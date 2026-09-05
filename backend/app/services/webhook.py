from sqlalchemy.orm import Session
from app.models import Payment, RecoveryCase, AuditEvent, Customer
from app.schemas import CaseState, PaymentStatus
from app.providers import get_payment_provider
from app.scheduler import scheduler
from app.services.audit import AuditService
import uuid

class WebhookService:
    @staticmethod
    def process_razorpay_event(db: Session, event_payload: dict) -> dict:
        """
        Handles parsed Razorpay webhook events, implements idempotency,
        transitions states, and cancels pending actions on successful recovery.
        """
        from app.state_machine import StateMachine
        provider = get_payment_provider()
        event_data = provider.parse_webhook(event_payload)
        
        event_id = event_data["event_id"]
        event_type = event_data["event_type"]
        payment_id = event_data["payment_id"]
        amount = event_data["amount"]
        rzp_payment_id = event_data["razorpay_payment_id"]

        # 1. Idempotency Check
        existing_event = db.query(AuditEvent).filter(AuditEvent.id == event_id).first()
        if existing_event:
            return {
                "status": "ignored",
                "reason": "Duplicate webhook event, already processed.",
                "event_id": event_id
            }

        # 2. Process event based on type
        if event_type == "payment.captured":
            # Find payment and recovery case
            payment = db.query(Payment).filter(Payment.id == payment_id).first()
            if not payment:
                # If payment isn't in DB, search by razorpay payment ID
                payment = db.query(Payment).filter(Payment.razorpay_payment_id == rzp_payment_id).first()
                
            if not payment:
                return {"status": "ignored", "reason": f"Payment not found for id: {payment_id}"}

            case = db.query(RecoveryCase).filter(RecoveryCase.payment_id == payment.id).first()
            if not case:
                return {"status": "ignored", "reason": f"Active recovery case not found for payment: {payment.id}"}

            # Update payment status
            payment.status = PaymentStatus.CAPTURED.value
            payment.razorpay_payment_id = rzp_payment_id
            db.commit()

            # Record capture audit log
            # We set AuditEvent.id to the webhook event_id for idempotency tracking!
            AuditService.log_event(
                db=db,
                case_id=case.id,
                event_type="PAYMENT_CAPTURED",
                result_status="success",
                metadata={"event_id": event_id, "amount": amount, "razorpay_payment_id": rzp_payment_id}
            )
            # Rewrite AuditEvent ID to enforce idempotency
            evt = db.query(AuditEvent).filter(AuditEvent.case_id == case.id, AuditEvent.event_type == "PAYMENT_CAPTURED").order_by(AuditEvent.timestamp.desc()).first()
            if evt:
                db.delete(evt)
                db.commit()
                # Create with exact event_id
                evt_new = AuditEvent(
                    id=event_id,
                    case_id=case.id,
                    event_type="PAYMENT_CAPTURED",
                    result_status="success",
                    metadata_json={"amount": amount, "razorpay_payment_id": rzp_payment_id}
                )
                db.add(evt_new)
                db.commit()

            # Transition state machine to RECOVERED (terminal state)
            StateMachine.transition_to(
                db=db,
                case=case,
                new_state=CaseState.RECOVERED,
                reason="Webhook confirmed payment completion"
            )

            # Race condition protection: cancel scheduled retries
            cancelled_count = scheduler.cancel_pending_actions(db, case.id)
            if cancelled_count > 0:
                AuditService.log_event(
                    db=db,
                    case_id=case.id,
                    event_type="PENDING_RETRY_CANCELLED",
                    metadata={"cancelled_actions_count": cancelled_count}
                )

            return {
                "status": "processed",
                "action": "recovered",
                "case_id": case.id,
                "cancelled_retries": cancelled_count
            }

        elif event_type == "payment.failed":
            # Retrieve payment and case
            payment = db.query(Payment).filter(Payment.id == payment_id).first()
            if not payment:
                return {"status": "ignored", "reason": f"Payment not found for id: {payment_id}"}

            case = db.query(RecoveryCase).filter(RecoveryCase.payment_id == payment.id).first()
            
            # If no recovery case exists, initialize one
            if not case:
                case_id = f"case_{uuid.uuid4().hex[:12]}"
                case = RecoveryCase(
                    id=case_id,
                    payment_id=payment.id,
                    customer_id=payment.customer_id,
                    state=CaseState.PAYMENT_FAILED.value,
                    risk_amount=payment.amount,
                    failure_reason=event_data.get("failure_description") or payment.failure_description or "UNKNOWN"
                )
                db.add(case)
                db.commit()
                db.refresh(case)

                # Log failure
                evt_new = AuditEvent(
                    id=event_id,
                    case_id=case.id,
                    event_type="PAYMENT_FAILED",
                    original_error=case.failure_reason,
                    metadata_json={"amount": payment.amount, "failure_code": event_data.get("failure_code")}
                )
                db.add(evt_new)
                db.commit()

                # Transition to DIAGNOSING to start recovery flow
                StateMachine.transition_to(
                    db=db,
                    case=case,
                    new_state=CaseState.DIAGNOSING,
                    reason="Created recovery case for failed payment"
                )

                return {
                    "status": "processed",
                    "action": "case_created",
                    "case_id": case.id
                }
            else:
                # If recovery case already exists, log failure event (this was a failed retry attempt)
                evt_new = AuditEvent(
                    id=event_id,
                    case_id=case.id,
                    event_type="PAYMENT_FAILED",
                    original_error=event_data.get("failure_description") or "Retry attempt failed",
                    metadata_json={"amount": payment.amount, "failure_code": event_data.get("failure_code")}
                )
                db.add(evt_new)
                db.commit()

                # Check retry limits
                if case.attempt_count >= case.max_attempts:
                    StateMachine.transition_to(
                        db=db,
                        case=case,
                        new_state=CaseState.MAX_ATTEMPTS,
                        reason="Max retry limits reached"
                    )
                else:
                    # Transition back to diagnosing to evaluate next options
                    StateMachine.transition_to(
                        db=db,
                        case=case,
                        new_state=CaseState.DIAGNOSING,
                        reason="Retry payment failed, re-diagnosing next action"
                    )

                return {
                    "status": "processed",
                    "action": "retry_failed",
                    "case_id": case.id
                }

        return {"status": "ignored", "reason": f"Unhandled event type: {event_type}"}
