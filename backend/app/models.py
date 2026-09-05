import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database import Base

class Customer(Base):
    __tablename__ = "customers"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    preferred_channel = Column(String, default="EMAIL")  # EMAIL, SMS, WHATSAPP
    salary_cycle_hint = Column(String, nullable=True)     # e.g., "1st-5th", "25th-30th"
    payment_behavior = Column(String, nullable=True)      # e.g., "prompt", "occasional_fails", "high_fails"
    opted_out = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    payments = relationship("Payment", back_populates="customer")
    recovery_cases = relationship("RecoveryCase", back_populates="customer")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True)
    razorpay_payment_id = Column(String, nullable=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    amount = Column(Float, nullable=False)  # In INR
    currency = Column(String, default="INR")
    status = Column(String, default="failed")  # failed, captured, refunded, created
    failure_code = Column(String, nullable=True)
    failure_description = Column(String, nullable=True)
    payment_type = Column(String, nullable=False)  # ONE_TIME, RECURRING, INVOICE
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    customer = relationship("Customer", back_populates="payments")
    recovery_case = relationship("RecoveryCase", back_populates="payment", uselist=False)


class RecoveryCase(Base):
    __tablename__ = "recovery_cases"

    id = Column(String, primary_key=True)
    payment_id = Column(String, ForeignKey("payments.id"), nullable=False, unique=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    state = Column(String, nullable=False, default="PAYMENT_FAILED")  # PAYMENT_FAILED, DIAGNOSING, RECOVERY_PLANNED, WAITING, RECOVERED, etc.
    risk_amount = Column(Float, nullable=False)
    failure_reason = Column(String, nullable=False)
    
    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    
    recommended_action = Column(String, nullable=True)
    next_action = Column(String, nullable=True)
    next_action_at = Column(DateTime, nullable=True)
    
    ai_diagnosis = Column(String, nullable=True)
    ai_confidence = Column(Float, nullable=True)
    ai_reasoning = Column(String, nullable=True)
    
    disputed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    customer = relationship("Customer", back_populates="recovery_cases")
    payment = relationship("Payment", back_populates="recovery_case")
    actions = relationship("RecoveryAction", back_populates="case", cascade="all, delete-orphan")
    audit_events = relationship("AuditEvent", back_populates="case", cascade="all, delete-orphan")


class RecoveryAction(Base):
    __tablename__ = "recovery_actions"

    id = Column(String, primary_key=True)
    case_id = Column(String, ForeignKey("recovery_cases.id"), nullable=False)
    action_type = Column(String, nullable=False)  # RETRY_PAYMENT, CREATE_PAYMENT_LINK, SEND_NOTIFICATION, SCHEDULE_RETRY, CANCEL_RETRY, ESCALATE, CLOSE_CASE
    status = Column(String, nullable=False, default="scheduled")  # scheduled, executing, success, failed
    scheduled_at = Column(DateTime, default=datetime.datetime.utcnow)
    executed_at = Column(DateTime, nullable=True)
    
    payload = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    failure_reason = Column(String, nullable=True)

    case = relationship("RecoveryCase", back_populates="actions")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String, primary_key=True)
    case_id = Column(String, ForeignKey("recovery_cases.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    event_type = Column(String, nullable=False)  # PAYMENT_FAILED, DIAGNOSIS_CREATED, ACTION_RECOMMENDED, POLICY_APPROVED, POLICY_REJECTED, etc.
    
    original_error = Column(String, nullable=True)
    agent_diagnosis = Column(String, nullable=True)
    intervention_chosen = Column(String, nullable=True)
    action_payload = Column(JSON, nullable=True)
    result_status = Column(String, nullable=True)
    metadata_json = Column(JSON, nullable=True)

    case = relationship("RecoveryCase", back_populates="audit_events")
