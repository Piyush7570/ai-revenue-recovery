from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, EmailStr
from enum import Enum

# --- Enums ---
class PaymentType(str, Enum):
    ONE_TIME = "ONE_TIME"
    RECURRING = "RECURRING"
    INVOICE = "INVOICE"

class PaymentStatus(str, Enum):
    FAILED = "failed"
    CAPTURED = "captured"
    REFUNDED = "refunded"
    CREATED = "created"

class CaseState(str, Enum):
    PAYMENT_FAILED = "PAYMENT_FAILED"
    DIAGNOSING = "DIAGNOSING"
    RECOVERY_PLANNED = "RECOVERY_PLANNED"
    ACTION_PENDING = "ACTION_PENDING"
    WAITING = "WAITING"
    RECOVERED = "RECOVERED"
    EXPIRED = "EXPIRED"
    MAX_ATTEMPTS = "MAX_ATTEMPTS"
    CUSTOMER_DECLINED = "CUSTOMER_DECLINED"
    DISPUTED = "DISPUTED"
    CANCELLED = "CANCELLED"
    ESCALATED = "ESCALATED"

class ActionType(str, Enum):
    RETRY_PAYMENT = "RETRY_PAYMENT"
    CREATE_PAYMENT_LINK = "CREATE_PAYMENT_LINK"
    SEND_NOTIFICATION = "SEND_NOTIFICATION"
    SCHEDULE_RETRY = "SCHEDULE_RETRY"
    CANCEL_RETRY = "CANCEL_RETRY"
    ESCALATE = "ESCALATE"
    CLOSE_CASE = "CLOSE_CASE"

class ActionStatus(str, Enum):
    SCHEDULED = "scheduled"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"

class DiagnosisType(str, Enum):
    TRANSIENT_GATEWAY_ERROR = "TRANSIENT_GATEWAY_ERROR"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    EXPIRED_PAYMENT_METHOD = "EXPIRED_PAYMENT_METHOD"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
    CUSTOMER_FRICTION = "CUSTOMER_FRICTION"
    CHECKOUT_ABANDONMENT = "CHECKOUT_ABANDONMENT"
    UNKNOWN = "UNKNOWN"

class RecommendedActionType(str, Enum):
    RETRY_PAYMENT = "RETRY_PAYMENT"
    CREATE_PAYMENT_LINK = "CREATE_PAYMENT_LINK"
    WAIT_AND_RETRY = "WAIT_AND_RETRY"
    SEND_NOTIFICATION = "SEND_NOTIFICATION"
    ESCALATE = "ESCALATE"
    NO_ACTION = "NO_ACTION"

class CustomerReplyIntent(str, Enum):
    PROMISE_TO_PAY = "PROMISE_TO_PAY"
    DISPUTE = "DISPUTE"
    OPT_OUT = "OPT_OUT"
    OTHER = "OTHER"

# --- Customer Schemas ---
class CustomerBase(BaseModel):
    name: str
    email: str
    phone: str
    preferred_channel: str = "EMAIL"
    salary_cycle_hint: Optional[str] = None
    payment_behavior: Optional[str] = None
    opted_out: bool = False

class CustomerCreate(CustomerBase):
    id: str

class CustomerResponse(CustomerBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True

# --- Payment Schemas ---
class PaymentBase(BaseModel):
    customer_id: str
    amount: float
    currency: str = "INR"
    status: PaymentStatus = PaymentStatus.FAILED
    failure_code: Optional[str] = None
    failure_description: Optional[str] = None
    payment_type: PaymentType

class PaymentCreate(PaymentBase):
    id: str
    razorpay_payment_id: Optional[str] = None

class PaymentResponse(PaymentBase):
    id: str
    razorpay_payment_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Action Schemas ---
class RecoveryActionBase(BaseModel):
    action_type: ActionType
    status: ActionStatus = ActionStatus.SCHEDULED
    scheduled_at: datetime
    executed_at: Optional[datetime] = None
    payload: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    failure_reason: Optional[str] = None

class RecoveryActionResponse(RecoveryActionBase):
    id: str
    case_id: str

    class Config:
        from_attributes = True

# --- Audit Event Schemas ---
class AuditEventBase(BaseModel):
    event_type: str
    timestamp: datetime
    original_error: Optional[str] = None
    agent_diagnosis: Optional[str] = None
    intervention_chosen: Optional[str] = None
    action_payload: Optional[Dict[str, Any]] = None
    result_status: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None

class AuditEventResponse(AuditEventBase):
    id: str
    case_id: str

    class Config:
        from_attributes = True

# --- Recovery Case Schemas ---
class RecoveryCaseBase(BaseModel):
    payment_id: str
    customer_id: str
    state: CaseState = CaseState.PAYMENT_FAILED
    risk_amount: float
    failure_reason: str
    attempt_count: int = 0
    max_attempts: int = 3
    recommended_action: Optional[str] = None
    next_action: Optional[str] = None
    next_action_at: Optional[datetime] = None
    ai_diagnosis: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_reasoning: Optional[str] = None
    disputed: bool = False
    closed_at: Optional[datetime] = None

class RecoveryCaseResponse(RecoveryCaseBase):
    id: str
    created_at: datetime
    updated_at: datetime
    customer: CustomerResponse
    payment: PaymentResponse
    actions: List[RecoveryActionResponse] = []
    audit_events: List[AuditEventResponse] = []

    class Config:
        from_attributes = True

# --- AI Decision structured output validation ---
class AIDecisionSchema(BaseModel):
    diagnosis: DiagnosisType
    confidence: float = Field(..., ge=0.0, le=1.0)
    recommended_action: RecommendedActionType
    delay_hours: int = Field(default=0, ge=0)
    reason: str
    message_intent: str
    message_content: str

class AICustomerReplySchema(BaseModel):
    intent: CustomerReplyIntent
    promised_date: Optional[str] = Field(default=None, description="ISO format date YYYY-MM-DD if intent is PROMISE_TO_PAY")
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str

# --- Simulation endpoints payload ---
class SimulateFailureRequest(BaseModel):
    customer_id: Optional[str] = None
    amount: float
    payment_type: PaymentType
    failure_code: str
    failure_description: str

class SimulateSuccessRequest(BaseModel):
    case_id: str

class CustomerReplyRequest(BaseModel):
    reply_text: str

# --- Evaluation Schemas ---
class MetricSummary(BaseModel):
    recovered_inr: float
    total_at_risk_inr: float
    recovery_rate_inr: float
    recovered_cases: int
    total_cases: int
    recovery_rate_count: float
    recovery_attempt_overhead: float  # total_attempts / recovered_cases
    avg_attempts_per_case: float      # total_attempts / total_cases
    unnecessary_retry_rate: float
    operational_recovery_cost: float  # sum of retry/notification/escalation fees
    false_positive_cost: float        # cost of unnecessary/incorrect actions compared with ground truth
    avg_time_to_recovery_hours: float
    diagnosis_accuracy: float
    action_accuracy: float

class EvaluationResults(BaseModel):
    baseline: MetricSummary
    ai_recovery: MetricSummary
    cases_run: int
    dataset_size: int
    random_seed: int
    execution_mode: str
