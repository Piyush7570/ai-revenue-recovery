import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base
from app.models import Customer, Payment, RecoveryCase, RecoveryAction, AuditEvent
from app.schemas import CaseState, ActionType, ActionStatus, PaymentStatus, PaymentType, DiagnosisType, RecommendedActionType
from app.state_machine import StateMachine
from app.policy_engine import PolicyEngine
from app.services.webhook import WebhookService
from app.services.evaluation import EvaluationEngine
from app.ai import LLMService

# In-memory database setup for testing
DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

# 1. State Machine Tests
def test_state_machine_transitions(db):
    cust = Customer(id="c_1", name="Test Customer", email="t@example.com", phone="123", preferred_channel="EMAIL")
    pay = Payment(id="p_1", customer_id="c_1", amount=100.0, status="failed", payment_type="ONE_TIME")
    db.add_all([cust, pay])
    db.commit()

    case = RecoveryCase(id="case_1", payment_id="p_1", customer_id="c_1", state=CaseState.PAYMENT_FAILED.value, risk_amount=100.0, failure_reason="FAIL")
    db.add(case)
    db.commit()

    # Valid transitions: PAYMENT_FAILED -> DIAGNOSING
    StateMachine.transition_to(db, case, CaseState.DIAGNOSING)
    assert case.state == CaseState.DIAGNOSING.value

    # Valid transitions: DIAGNOSING -> RECOVERY_PLANNED
    StateMachine.transition_to(db, case, CaseState.RECOVERY_PLANNED)
    assert case.state == CaseState.RECOVERY_PLANNED.value

    # Invalid transition: RECOVERY_PLANNED -> PAYMENT_FAILED (raises ValueError)
    with pytest.raises(ValueError):
        StateMachine.transition_to(db, case, CaseState.PAYMENT_FAILED)

# 2. Safety / Policy Engine Tests
def test_policy_engine_max_attempts(db):
    cust = Customer(id="c_1", name="Test Customer", email="t@example.com", phone="123", preferred_channel="EMAIL")
    pay = Payment(id="p_1", customer_id="c_1", amount=100.0, status="failed", payment_type="RECURRING")
    db.add_all([cust, pay])
    db.commit()

    case = RecoveryCase(
        id="case_1", payment_id="p_1", customer_id="c_1", 
        state=CaseState.WAITING.value, risk_amount=100.0, 
        failure_reason="LOW_BALANCE", attempt_count=3, max_attempts=3
    )
    db.add(case)
    db.commit()

    # Try validating a scheduled retry when limit is reached
    approved, reason = PolicyEngine.validate_action(db, case, ActionType.RETRY_PAYMENT)
    assert not approved
    assert "Maximum retry attempts reached" in reason

def test_policy_engine_customer_opt_out(db):
    cust = Customer(id="c_1", name="Test Customer", email="t@example.com", phone="123", preferred_channel="EMAIL", opted_out=True)
    pay = Payment(id="p_1", customer_id="c_1", amount=100.0, status="failed", payment_type="ONE_TIME")
    db.add_all([cust, pay])
    db.commit()

    case = RecoveryCase(id="case_1", payment_id="p_1", customer_id="c_1", state=CaseState.WAITING.value, risk_amount=100.0, failure_reason="FAIL")
    db.add(case)
    db.commit()

    approved, reason = PolicyEngine.validate_action(db, case, ActionType.SEND_NOTIFICATION)
    assert not approved
    assert "Customer has opted out" in reason

# 3. Idempotency Tests
def test_webhook_idempotency(db):
    cust = Customer(id="c_1", name="Test Customer", email="t@example.com", phone="123", preferred_channel="EMAIL")
    pay = Payment(id="p_1", customer_id="c_1", amount=100.0, status="failed", payment_type="ONE_TIME")
    db.add_all([cust, pay])
    db.commit()

    # Define a captured event payload
    event_payload = {
        "id": "evt_test_idempotency_123",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_external_123",
                    "amount": 10000,
                    "currency": "INR",
                    "status": "captured",
                    "notes": {
                        "internal_payment_id": "p_1"
                    }
                }
            }
        }
    }

    # Initialize case
    case = RecoveryCase(id="case_1", payment_id="p_1", customer_id="c_1", state=CaseState.WAITING.value, risk_amount=100.0, failure_reason="FAIL")
    db.add(case)
    db.commit()

    # Process first time
    res = WebhookService.process_razorpay_event(db, event_payload)
    assert res["status"] == "processed"
    assert case.state == CaseState.RECOVERED.value

    # Process second time (should be ignored due to duplicate webhook event)
    res2 = WebhookService.process_razorpay_event(db, event_payload)
    assert res2["status"] == "ignored"
    assert "Duplicate webhook" in res2["reason"]

# 4. Race Condition Protection Tests
def test_race_condition_retry_cancellation(db):
    cust = Customer(id="c_1", name="Test Customer", email="t@example.com", phone="123", preferred_channel="EMAIL")
    pay = Payment(id="p_1", customer_id="c_1", amount=100.0, status="failed", payment_type="RECURRING")
    db.add_all([cust, pay])
    db.commit()

    case = RecoveryCase(id="case_1", payment_id="p_1", customer_id="c_1", state=CaseState.WAITING.value, risk_amount=100.0, failure_reason="LOW_BALANCE")
    db.add(case)
    db.commit()

    # Add a scheduled action
    act = RecoveryAction(id="act_1", case_id="case_1", action_type=ActionType.RETRY_PAYMENT.value, status=ActionStatus.SCHEDULED.value, scheduled_at=datetime.datetime.utcnow())
    db.add(act)
    db.commit()

    # Customer makes manual payment (webhook triggers recovery)
    event_payload = {
        "id": "evt_capture_456",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_external_456",
                    "amount": 10000,
                    "currency": "INR",
                    "status": "captured",
                    "notes": {
                        "internal_payment_id": "p_1"
                    }
                }
            }
        }
    }

    res = WebhookService.process_razorpay_event(db, event_payload)
    assert res["status"] == "processed"
    assert res["cancelled_retries"] == 1
    
    # Re-query action: must be cancelled (failed/cancelled status)
    db.refresh(act)
    assert act.status == ActionStatus.FAILED.value
    assert "Cancelled" in act.failure_reason

# 5. AI Validation Tests
def test_ai_fallback_diagnoses():
    assert LLMService.get_diagnosis_fallback("INSUFFICIENT_FUNDS") == DiagnosisType.INSUFFICIENT_FUNDS
    assert LLMService.get_diagnosis_fallback("CARD_EXPIRED") == DiagnosisType.EXPIRED_PAYMENT_METHOD
    assert LLMService.get_diagnosis_fallback("GATEWAY_TIMEOUT") == DiagnosisType.TRANSIENT_GATEWAY_ERROR

def test_evaluation_reproducible_math():
    results = EvaluationEngine.run_evaluation()
    
    # Verify synthetic cases run and metadata
    assert results.cases_run == 50
    assert results.dataset_size == 50
    assert results.random_seed == 42
    assert results.baseline.total_cases == 50
    assert results.ai_recovery.total_cases == 50
    
    # AI recovery rate should be higher than baseline
    assert results.ai_recovery.recovery_rate_inr >= results.baseline.recovery_rate_inr
    # AI unnecessary retries should be 0 or very low, baseline has higher
    assert results.ai_recovery.unnecessary_retry_rate <= results.baseline.unnecessary_retry_rate
    
    # Cost splits validation
    assert results.baseline.operational_recovery_cost > 0
    assert results.baseline.false_positive_cost > 0
    # In AI, false positive cost should be 0 because of perfect ground-truth diagnosis match
    assert results.ai_recovery.false_positive_cost == 0
    # Average attempts per case vs recovery attempt overhead
    assert results.baseline.avg_attempts_per_case <= 3.0
    assert results.baseline.recovery_attempt_overhead >= 3.0

def test_race_condition_policy_rejection(db):
    cust = Customer(id="c_1", name="Test Customer", email="t@example.com", phone="123", preferred_channel="EMAIL")
    pay = Payment(id="p_1", customer_id="c_1", amount=100.0, status="captured", payment_type="RECURRING") # Already captured
    db.add_all([cust, pay])
    db.commit()

    case = RecoveryCase(id="case_1", payment_id="p_1", customer_id="c_1", state=CaseState.RECOVERED.value, risk_amount=100.0, failure_reason="LOW_BALANCE")
    db.add(case)
    db.commit()

    # Policy engine should block any retry action since payment is captured and case is RECOVERED
    approved, reason = PolicyEngine.validate_action(db, case, ActionType.RETRY_PAYMENT)
    assert not approved
    assert "terminal state" in reason or "succeeded" in reason

