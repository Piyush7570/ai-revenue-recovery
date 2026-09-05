import datetime
from fastapi import FastAPI, Depends, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from app.config import settings
from app.database import get_db, init_db, engine, SessionLocal
from app.models import Customer, Payment, RecoveryCase, RecoveryAction, AuditEvent, Base
from app.schemas import (
    RecoveryCaseResponse, AIDecisionSchema, CaseState, ActionType,
    SimulateFailureRequest, SimulateSuccessRequest, CustomerReplyRequest,
    EvaluationResults, RecommendedActionType, CustomerReplyIntent, DiagnosisType
)
from app.state_machine import StateMachine
from app.policy_engine import PolicyEngine
from app.action_executor import ActionExecutor
from app.scheduler import scheduler
from app.ai import LLMService
from app.services import WebhookService, AuditService, EvaluationEngine
from app.providers import get_payment_provider
from app.providers.simulation import SimulationProvider

# Create FastAPI app
app = FastAPI(title="PayRevive API — AI Revenue Recovery System", version="1.0.0")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup event to initialize DB & start scheduler
@app.on_event("startup")
def startup_event():
    init_db()
    scheduler.start(run_interval_seconds=1)
    
    # Seed data if DB is empty
    db = SessionLocal()
    try:
        if db.query(Customer).count() == 0:
            seed_initial_data(db)
    finally:
        db.close()

@app.on_event("shutdown")
def shutdown_event():
    scheduler.stop()

# Helper to seed data
def seed_initial_data(db: Session):
    # Customers
    cust1 = Customer(id="cust_001", name="Aarav Mehta", email="aarav@example.com", phone="+919876543210", preferred_channel="EMAIL", payment_behavior="prompt")
    cust2 = Customer(id="cust_002", name="Ishita Sen", email="ishita@example.com", phone="+919876543211", preferred_channel="SMS", payment_behavior="occasional_fails")
    cust3 = Customer(id="cust_003", name="Kabir Singh", email="kabir@example.com", phone="+919876543212", preferred_channel="WHATSAPP", payment_behavior="high_fails")
    cust4 = Customer(id="cust_004", name="Riya Sharma", email="riya@example.com", phone="+919876543213", preferred_channel="EMAIL", payment_behavior="prompt")
    cust5 = Customer(id="cust_005", name="Grace Outage User", email="grace@example.com", phone="+919876543214", preferred_channel="EMAIL", payment_behavior="occasional_fails") # triggers provider API failure demo
    
    db.add_all([cust1, cust2, cust3, cust4, cust5])
    db.commit()

    # Payments (Failed)
    p1 = Payment(id="pay_001", customer_id="cust_001", amount=2499.0, status="failed", failure_code="INSUFFICIENT_FUNDS", failure_description="The card has insufficient funds.", payment_type="RECURRING")
    p2 = Payment(id="pay_002", customer_id="cust_002", amount=799.0, status="failed", failure_code="GATEWAY_ERROR", failure_description="Acquirer gateway was down during auth.", payment_type="ONE_TIME")
    p3 = Payment(id="pay_003", customer_id="cust_003", amount=4999.0, status="failed", failure_code="EXPIRED_CARD", failure_description="Card has expired.", payment_type="RECURRING")
    p4 = Payment(id="pay_004", customer_id="cust_004", amount=1299.0, status="failed", failure_code="CHECKOUT_ABANDONED", failure_description="Customer abandoned checkout flow.", payment_type="ONE_TIME")
    p5 = Payment(id="pay_005", customer_id="cust_005", amount=1337.0, status="failed", failure_code="INSUFFICIENT_FUNDS", failure_description="Demo case triggering API error.", payment_type="RECURRING")
    
    db.add_all([p1, p2, p3, p4, p5])
    db.commit()

    # Recovery cases initial webhooks simulation
    for p in [p1, p2, p3, p4, p5]:
        mock_payload = SimulationProvider.generate_webhook_payload(
            event_type="payment.failed",
            internal_payment_id=p.id,
            amount=p.amount,
            error_code=p.failure_code,
            error_description=p.failure_description
        )
        WebhookService.process_razorpay_event(db, mock_payload)


# --- REST API Endpoints ---

@app.get("/api/dashboard/summary")
def get_dashboard_summary(db: Session = Depends(get_db)):
    """
    Returns merchant dashboard summary statistics.
    """
    total_cases = db.query(RecoveryCase).count()
    active_cases = db.query(RecoveryCase).filter(
        ~RecoveryCase.state.in_(StateMachine.TERMINAL_STATES)
    ).count()
    
    recovered_cases = db.query(RecoveryCase).filter(
        RecoveryCase.state == CaseState.RECOVERED.value
    ).count()

    total_risk_amount = db.query(RecoveryCase).with_entities(
        RecoveryCase.risk_amount
    ).all()
    at_risk_inr = sum(c[0] for c in total_risk_amount)

    recovered_amount_list = db.query(RecoveryCase).filter(
        RecoveryCase.state == CaseState.RECOVERED.value
    ).with_entities(RecoveryCase.risk_amount).all()
    recovered_inr = sum(c[0] for c in recovered_amount_list)
    
    recovery_rate = (recovered_inr / at_risk_inr * 100) if at_risk_inr > 0 else 0.0

    # Group by failure reasons
    reasons_data = {}
    cases = db.query(RecoveryCase).all()
    for c in cases:
        diag = c.ai_diagnosis or "DIAGNOSING"
        reasons_data[diag] = reasons_data.get(diag, 0) + 1

    # Group by strategies
    strategies_data = {}
    for c in cases:
        strat = c.recommended_action or "NO_ACTION"
        strategies_data[strat] = strategies_data.get(strat, 0) + 1

    # Total attempts count
    total_retries = db.query(RecoveryAction).filter(
        RecoveryAction.action_type == ActionType.RETRY_PAYMENT.value,
        RecoveryAction.status == "success"
    ).count()

    return {
        "revenue_at_risk": at_risk_inr,
        "revenue_recovered": recovered_inr,
        "recovery_rate": recovery_rate,
        "total_cases": total_cases,
        "active_cases": active_cases,
        "recovered_cases_count": recovered_cases,
        "total_interventions": total_retries,
        "failure_distribution": [{"name": k, "value": v} for k, v in reasons_data.items()],
        "strategy_distribution": [{"name": k, "value": v} for k, v in strategies_data.items()]
    }


@app.get("/api/recovery-cases", response_model=List[RecoveryCaseResponse])
def get_recovery_cases(
    state: Optional[str] = None,
    failure_reason: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Lists all recovery cases. Supports filtering.
    """
    query = db.query(RecoveryCase)
    if state:
        query = query.filter(RecoveryCase.state == state)
    if failure_reason:
        query = query.filter(RecoveryCase.failure_reason == failure_reason)
    
    # Sort newest cases first
    return query.order_by(RecoveryCase.created_at.desc()).all()


@app.get("/api/recovery-cases/{case_id}", response_model=RecoveryCaseResponse)
def get_recovery_case(case_id: str, db: Session = Depends(get_db)):
    """
    Returns detailed configuration and history of a recovery case.
    """
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Recovery Case not found")
    return case


@app.post("/api/recovery-cases/{case_id}/run")
def run_recovery_case(case_id: str, db: Session = Depends(get_db)):
    """
    Runs the AI diagnosis and immediately schedules/executes recovery actions.
    This behaves as the single-click "Run Recovery" trigger.
    """
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if case.state in StateMachine.TERMINAL_STATES:
         raise HTTPException(status_code=400, detail="Cannot run recovery on terminal cases")

    # 1. AI Diagnosis Layer
    payment_context = {
        "amount": case.payment.amount,
        "currency": case.payment.currency,
        "failure_code": case.payment.failure_code or "UNKNOWN",
        "failure_description": case.payment.failure_description or "Unknown failure reason"
    }
    customer_context = {
        "name": case.customer.name,
        "preferred_channel": case.customer.preferred_channel
    }

    # Transition to DIAGNOSING
    StateMachine.transition_to(
        db, case, CaseState.DIAGNOSING, 
        reason="Triggered AI diagnosis engine execution"
    )

    decision: AIDecisionSchema = LLMService.diagnose_and_recommend(
        payment_context=payment_context,
        customer_context=customer_context,
        attempt_count=case.attempt_count
    )

    # 2. Record Diagnosis and Recommendation
    case.ai_diagnosis = decision.diagnosis.value
    case.ai_confidence = decision.confidence
    case.ai_reasoning = decision.reason
    case.recommended_action = decision.recommended_action.value
    db.commit()

    AuditService.log_event(
        db=db,
        case_id=case.id,
        event_type="DIAGNOSIS_CREATED",
        agent_diagnosis=decision.diagnosis.value,
        metadata={"confidence": decision.confidence, "reasoning": decision.reason}
    )

    # If AI decides NO_ACTION, transition to waiting or escalate
    if decision.recommended_action == RecommendedActionType.NO_ACTION:
        StateMachine.transition_to(db, case, CaseState.WAITING, reason="AI recommended NO_ACTION at this stage.")
        return {"status": "success", "recommended_action": "NO_ACTION", "reason": decision.reason}

    # 3. Schedule or Execute approved action
    # Map AI recommendation to internal actions
    action_map = {
        RecommendedActionType.RETRY_PAYMENT: ActionType.RETRY_PAYMENT,
        RecommendedActionType.CREATE_PAYMENT_LINK: ActionType.CREATE_PAYMENT_LINK,
        RecommendedActionType.WAIT_AND_RETRY: ActionType.SCHEDULE_RETRY,
        RecommendedActionType.SEND_NOTIFICATION: ActionType.SEND_NOTIFICATION,
        RecommendedActionType.ESCALATE: ActionType.ESCALATE
    }
    action_type = action_map.get(decision.recommended_action)

    # Transition to RECOVERY_PLANNED
    StateMachine.transition_to(
        db, case, CaseState.RECOVERY_PLANNED,
        reason=f"Planned recovery strategy: {action_type.value}"
    )

    # Calculate run time (if delay_hours is set)
    run_at = datetime.datetime.utcnow() + datetime.timedelta(hours=decision.delay_hours)
    
    # Save action in DB
    action_payload = {
        "message": decision.message_content,
        "delay_hours": decision.delay_hours
    }
    action_id = scheduler.schedule_action(db, case.id, action_type, run_at, action_payload)

    AuditService.log_event(
        db=db,
        case_id=case.id,
        event_type="ACTION_RECOMMENDED",
        intervention_chosen=action_type.value,
        action_payload=action_payload,
        metadata={"action_id": action_id, "run_at": run_at.isoformat()}
    )

    # In DEMO MODE, if scheduled immediately (delay = 0), let's execute synchronously so UI is responsive!
    if decision.delay_hours == 0:
        ActionExecutor.execute_action(db, action_id)

    return {
        "status": "success",
        "action_id": action_id,
        "diagnosis": decision.diagnosis.value,
        "recommended_action": action_type.value,
        "delay_hours": decision.delay_hours,
        "reason": decision.reason
    }


@app.post("/api/recovery-cases/{case_id}/approve")
def approve_action(case_id: str, db: Session = Depends(get_db)):
    """
    Manually overrides delay and executes the next pending scheduled action immediately.
    """
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    next_scheduled = db.query(RecoveryAction).filter(
        RecoveryAction.case_id == case_id,
        RecoveryAction.status == "scheduled"
    ).order_by(RecoveryAction.scheduled_at.asc()).first()

    if not next_scheduled:
        raise HTTPException(status_code=400, detail="No pending scheduled actions to approve")

    # Run action immediately
    ActionExecutor.execute_action(db, next_scheduled.id)
    return {"status": "executed", "action_id": next_scheduled.id}


@app.post("/api/recovery-cases/{case_id}/cancel")
def cancel_case(case_id: str, db: Session = Depends(get_db)):
    """
    Manually cancels an active recovery case.
    """
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    StateMachine.transition_to(db, case, CaseState.CANCELLED, reason="Cancelled manually by operator")
    scheduler.cancel_pending_actions(db, case.id)
    
    return {"status": "cancelled", "case_id": case_id}


@app.post("/api/recovery-cases/{case_id}/reply")
def simulate_customer_reply(case_id: str, payload: CustomerReplyRequest, db: Session = Depends(get_db)):
    """
    Simulates receiving a text reply from a customer.
    Parses intent using AI service and transitions case state.
    """
    case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Log reply
    AuditService.log_event(
        db=db,
        case_id=case.id,
        event_type="CUSTOMER_REPLY_RECEIVED",
        metadata={"reply_text": payload.reply_text}
    )

    # Invoke NLP interpretation
    ai_reply = LLMService.interpret_customer_reply(payload.reply_text)

    # Apply state transitions based on intent
    if ai_reply.intent == CustomerReplyIntent.OPT_OUT:
        # Opt out of notifications, cancel pending actions, mark customer opt-out
        case.customer.opted_out = True
        db.commit()
        StateMachine.transition_to(
            db, case, CaseState.CANCELLED,
            reason=f"Customer opt-out request detected: \"{payload.reply_text}\""
        )
        scheduler.cancel_pending_actions(db, case.id)

    elif ai_reply.intent == CustomerReplyIntent.DISPUTE:
        # Set dispute flag, cancel pending actions
        case.disputed = True
        db.commit()
        StateMachine.transition_to(
            db, case, CaseState.DISPUTED,
            reason=f"Customer transaction dispute request detected: \"{payload.reply_text}\""
        )
        scheduler.cancel_pending_actions(db, case.id)

    elif ai_reply.intent == CustomerReplyIntent.PROMISE_TO_PAY:
        # Update case state and shift next schedule action
        date_str = ai_reply.promised_date or (datetime.date.today() + datetime.timedelta(days=3)).isoformat()
        promised_dt = datetime.datetime.fromisoformat(date_str)
        
        # Schedule grace period check
        grace_dt = promised_dt + datetime.timedelta(days=1)
        
        # Update case schedule parameters
        case.next_action_at = grace_dt
        case.next_action = ActionType.SEND_NOTIFICATION.value
        db.commit()

        # Log promise
        AuditService.log_event(
            db=db,
            case_id=case.id,
            event_type="PROMISE_TO_PAY_RECORDED",
            metadata={"promised_date": date_str, "grace_period_check_at": grace_dt.isoformat()}
        )
        
        # Move state machine to WAITING
        StateMachine.transition_to(
            db, case, CaseState.WAITING,
            reason=f"Recorded Promise to Pay for {date_str}. Suppressed notifications until grace period check."
        )

    return {
        "intent": ai_reply.intent.value,
        "promised_date": ai_reply.promised_date,
        "confidence": ai_reply.confidence,
        "reason": ai_reply.reason
    }


@app.post("/api/webhooks/razorpay")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Ingests standard Razorpay webhook payloads. Enforces signature verification.
    """
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    
    # Verify Webhook
    provider = get_payment_provider()
    # Check signature authenticity
    if not provider.verify_webhook(body, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
    
    # Process event
    import json
    event_payload = json.loads(body.decode("utf-8"))
    res = WebhookService.process_razorpay_event(db, event_payload)
    
    # Duplicate webhook simulation
    from app.providers.simulation import SIMULATION_CONFIG
    if SIMULATION_CONFIG["duplicate_webhook_enabled"]:
        # Re-run process to verify idempotency blocks duplicate counts
        res = WebhookService.process_razorpay_event(db, event_payload)
        
    return res


# --- Simulation Helper Endpoints ---

@app.get("/api/simulation/config")
def get_simulation_config():
    from app.providers.simulation import SIMULATION_CONFIG
    return SIMULATION_CONFIG


@app.post("/api/simulation/config")
def update_simulation_config(config: dict):
    from app.providers.simulation import SIMULATION_CONFIG
    for k, v in config.items():
        if k in SIMULATION_CONFIG:
            SIMULATION_CONFIG[k] = bool(v)
    return SIMULATION_CONFIG


@app.post("/api/simulation/payment-failure")
def simulate_new_failure(payload: SimulateFailureRequest, db: Session = Depends(get_db)):
    """
    Simulates a new failed payment event coming from Razorpay, creating
    a Customer, failed Payment and triggering the webhook processor to start recovery.
    """
    cust_id = payload.customer_id or f"cust_{uuid.uuid4().hex[:6]}"
    customer = db.query(Customer).filter(Customer.id == cust_id).first()
    if not customer:
        customer = Customer(
            id=cust_id,
            name=f"Simulated User {uuid.uuid4().hex[:4]}",
            email=f"user_{uuid.uuid4().hex[:4]}@example.com",
            phone=f"+919{uuid.uuid4().hex[:9]}",
            preferred_channel="EMAIL"
        )
        db.add(customer)
        db.commit()

    payment_id = f"pay_{uuid.uuid4().hex[:12]}"
    payment = Payment(
        id=payment_id,
        customer_id=customer.id,
        amount=payload.amount,
        status="failed",
        failure_code=payload.failure_code,
        failure_description=payload.failure_description,
        payment_type=payload.payment_type.value
    )
    db.add(payment)
    db.commit()

    # Generate failed webhook payload
    mock_payload = SimulationProvider.generate_webhook_payload(
        event_type="payment.failed",
        internal_payment_id=payment.id,
        amount=payment.amount,
        error_code=payload.failure_code,
        error_description=payload.failure_description
    )

    res = WebhookService.process_razorpay_event(db, mock_payload)
    return {
        "payment_id": payment.id,
        "customer_id": customer.id,
        "webhook_result": res
    }


@app.post("/api/simulation/payment-success")
def simulate_customer_payment(payload: SimulateSuccessRequest, db: Session = Depends(get_db)):
    """
    Simulates a customer making a manual payment (e.g. paying via the recovery link).
    Triggers a payment.captured webhook payload to close the case.
    """
    case = db.query(RecoveryCase).filter(RecoveryCase.id == payload.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    mock_payload = SimulationProvider.generate_webhook_payload(
        event_type="payment.captured",
        internal_payment_id=case.payment.id,
        amount=case.payment.amount,
        razorpay_payment_id=f"pay_{uuid.uuid4().hex[:12]}"
    )

    # Process webhook
    res = WebhookService.process_razorpay_event(db, mock_payload)
    
    # Duplicate webhook simulation
    from app.providers.simulation import SIMULATION_CONFIG
    if SIMULATION_CONFIG["duplicate_webhook_enabled"]:
        res = WebhookService.process_razorpay_event(db, mock_payload)
        
    return {
        "webhook_result": res
    }


@app.post("/api/simulation/showcase/{scenario_name}")
def trigger_showcase(scenario_name: str, db: Session = Depends(get_db)):
    """
    Triggers deterministic showcases for evaluation and demo auditing.
    """
    from app.providers.simulation import SIMULATION_CONFIG
    
    if scenario_name == "insufficient_funds":
        cust_id = "showcase_cust_1"
        cust = db.query(Customer).filter(Customer.id == cust_id).first()
        if not cust:
            cust = Customer(id=cust_id, name="Rahul Verma", email="rahul.verma@example.com", phone="+919811122233", preferred_channel="EMAIL")
            db.add(cust)
            db.commit()
            
        p_id = f"pay_showcase_1_{uuid.uuid4().hex[:4]}"
        p = Payment(id=p_id, customer_id=cust_id, amount=2499.0, status="failed", failure_code="INSUFFICIENT_FUNDS", failure_description="The card has insufficient funds.", payment_type="RECURRING")
        db.add(p)
        db.commit()
        
        mock_payload = SimulationProvider.generate_webhook_payload(
            event_type="payment.failed",
            internal_payment_id=p.id,
            amount=p.amount,
            error_code=p.failure_code,
            error_description=p.failure_description
        )
        res = WebhookService.process_razorpay_event(db, mock_payload)
        case = db.query(RecoveryCase).filter(RecoveryCase.payment_id == p.id).first()
        return {"status": "created", "case_id": case.id, "payment_id": p.id, "scenario": "Insufficient Funds"}

    elif scenario_name == "gateway_error":
        cust_id = "showcase_cust_2"
        cust = db.query(Customer).filter(Customer.id == cust_id).first()
        if not cust:
            cust = Customer(id=cust_id, name="Sunita Rao", email="sunita.rao@example.com", phone="+919822233344", preferred_channel="SMS")
            db.add(cust)
            db.commit()
            
        p_id = f"pay_showcase_2_{uuid.uuid4().hex[:4]}"
        p = Payment(id=p_id, customer_id=cust_id, amount=799.0, status="failed", failure_code="GATEWAY_ERROR", failure_description="Gateway timeout on bank auth.", payment_type="ONE_TIME")
        db.add(p)
        db.commit()
        
        mock_payload = SimulationProvider.generate_webhook_payload(
            event_type="payment.failed",
            internal_payment_id=p.id,
            amount=p.amount,
            error_code=p.failure_code,
            error_description=p.failure_description
        )
        res = WebhookService.process_razorpay_event(db, mock_payload)
        case = db.query(RecoveryCase).filter(RecoveryCase.payment_id == p.id).first()
        return {"status": "created", "case_id": case.id, "payment_id": p.id, "scenario": "Gateway Error Retry"}

    elif scenario_name == "card_expired":
        cust_id = "showcase_cust_3"
        cust = db.query(Customer).filter(Customer.id == cust_id).first()
        if not cust:
            cust = Customer(id=cust_id, name="Vijay M.", email="vijay@example.com", phone="+919833344455", preferred_channel="WHATSAPP")
            db.add(cust)
            db.commit()
            
        p_id = f"pay_showcase_3_{uuid.uuid4().hex[:4]}"
        p = Payment(id=p_id, customer_id=cust_id, amount=4999.0, status="failed", failure_code="CARD_EXPIRED", failure_description="Card validation failed due to expiration date.", payment_type="RECURRING")
        db.add(p)
        db.commit()
        
        mock_payload = SimulationProvider.generate_webhook_payload(
            event_type="payment.failed",
            internal_payment_id=p.id,
            amount=p.amount,
            error_code=p.failure_code,
            error_description=p.failure_description
        )
        res = WebhookService.process_razorpay_event(db, mock_payload)
        case = db.query(RecoveryCase).filter(RecoveryCase.payment_id == p.id).first()
        return {"status": "created", "case_id": case.id, "payment_id": p.id, "scenario": "Card Expired"}

    elif scenario_name == "checkout_abandonment":
        cust_id = "showcase_cust_4"
        cust = db.query(Customer).filter(Customer.id == cust_id).first()
        if not cust:
            cust = Customer(id=cust_id, name="Preeti Joshi", email="preeti@example.com", phone="+919844455566", preferred_channel="EMAIL")
            db.add(cust)
            db.commit()
            
        p_id = f"pay_showcase_4_{uuid.uuid4().hex[:4]}"
        p = Payment(id=p_id, customer_id=cust_id, amount=1299.0, status="failed", failure_code="CHECKOUT_ABANDONED", failure_description="User left checkout page.", payment_type="ONE_TIME")
        db.add(p)
        db.commit()
        
        mock_payload = SimulationProvider.generate_webhook_payload(
            event_type="payment.failed",
            internal_payment_id=p.id,
            amount=p.amount,
            error_code=p.failure_code,
            error_description=p.failure_description
        )
        res = WebhookService.process_razorpay_event(db, mock_payload)
        case = db.query(RecoveryCase).filter(RecoveryCase.payment_id == p.id).first()
        return {"status": "created", "case_id": case.id, "payment_id": p.id, "scenario": "Checkout Abandonment"}

    elif scenario_name == "provider_outage":
        SIMULATION_CONFIG["outage_enabled"] = True
        
        cust_id = "showcase_cust_5"
        cust = db.query(Customer).filter(Customer.id == cust_id).first()
        if not cust:
            cust = Customer(id=cust_id, name="Anil Kapoor", email="anil@example.com", phone="+919855566677", preferred_channel="EMAIL")
            db.add(cust)
            db.commit()
            
        p_id = f"pay_showcase_5_{uuid.uuid4().hex[:4]}"
        p = Payment(id=p_id, customer_id=cust_id, amount=1337.0, status="failed", failure_code="INSUFFICIENT_FUNDS", failure_description="Gateway transaction outage check.", payment_type="RECURRING")
        db.add(p)
        db.commit()
        
        mock_payload = SimulationProvider.generate_webhook_payload(
            event_type="payment.failed",
            internal_payment_id=p.id,
            amount=p.amount,
            error_code=p.failure_code,
            error_description=p.failure_description
        )
        res = WebhookService.process_razorpay_event(db, mock_payload)
        case = db.query(RecoveryCase).filter(RecoveryCase.payment_id == p.id).first()
        return {"status": "created", "case_id": case.id, "payment_id": p.id, "scenario": "Provider Outage Fallback"}

    elif scenario_name == "race_condition":
        cust_id = "showcase_cust_6"
        cust = db.query(Customer).filter(Customer.id == cust_id).first()
        if not cust:
            cust = Customer(id=cust_id, name="Ramesh Kumar", email="ramesh@example.com", phone="+919866677788", preferred_channel="EMAIL")
            db.add(cust)
            db.commit()
            
        p_id = f"pay_showcase_6_{uuid.uuid4().hex[:4]}"
        p = Payment(id=p_id, customer_id=cust_id, amount=2499.0, status="failed", failure_code="GATEWAY_TIMEOUT", failure_description="Network transaction failure.", payment_type="RECURRING")
        db.add(p)
        db.commit()
        
        mock_payload = SimulationProvider.generate_webhook_payload(
            event_type="payment.failed",
            internal_payment_id=p.id,
            amount=p.amount,
            error_code=p.failure_code,
            error_description=p.failure_description
        )
        res = WebhookService.process_razorpay_event(db, mock_payload)
        case = db.query(RecoveryCase).filter(RecoveryCase.payment_id == p.id).first()
        if not case:
            raise HTTPException(status_code=500, detail="Failed to initialize showcase recovery case")
        
        case.state = CaseState.DIAGNOSING.value
        db.commit()
        
        case.ai_diagnosis = DiagnosisType.TRANSIENT_GATEWAY_ERROR.value
        case.ai_confidence = 0.90
        case.recommended_action = RecommendedActionType.WAIT_AND_RETRY.value
        case.next_action = ActionType.RETRY_PAYMENT.value
        case.next_action_at = datetime.datetime.utcnow() + datetime.timedelta(hours=2)
        case.state = CaseState.RECOVERY_PLANNED.value
        db.commit()
        
        action_id = f"act_race_{uuid.uuid4().hex[:8]}"
        action = RecoveryAction(
            id=action_id,
            case_id=case.id,
            action_type=ActionType.RETRY_PAYMENT.value,
            status="scheduled",
            payload={"message": "Retrying card charge after transient gateway failure."},
            scheduled_at=case.next_action_at
        )
        db.add(action)
        db.commit()
        
        AuditService.log_event(
            db=db,
            case_id=case.id,
            event_type="STATE_CHANGED",
            metadata={"from_state": "DIAGNOSING", "to_state": "RECOVERY_PLANNED", "reason": "Scheduled card retry in 2 hours"}
        )
        
        return {
            "status": "created", 
            "case_id": case.id, 
            "payment_id": p.id, 
            "action_id": action_id,
            "scenario": "Race Condition (Retry Scheduled)"
        }

    else:
        raise HTTPException(status_code=400, detail="Unknown showcase scenario")


@app.post("/api/evaluation/run", response_model=EvaluationResults)
def run_evaluation_metrics():
    """
    Runs baseline and AI models over the synthetic dataset.
    """
    return EvaluationEngine.run_evaluation()


@app.get("/api/evaluation/results", response_model=EvaluationResults)
def get_evaluation_metrics():
    """
    Returns results of evaluation. Runs dynamically to always match live data calculations.
    """
    return EvaluationEngine.run_evaluation()
