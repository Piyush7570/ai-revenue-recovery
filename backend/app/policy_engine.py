import datetime
from sqlalchemy.orm import Session
from app.models import RecoveryCase, RecoveryAction
from app.schemas import CaseState, ActionType, PaymentStatus
from app.config import settings
from app.services.audit import AuditService

class PolicyEngine:
    @staticmethod
    def validate_action(
        db: Session,
        case: RecoveryCase,
        action_type: ActionType,
        action_id: str = None
    ) -> tuple[bool, str]:
        """
        Validates if a recommended action is safe to execute based on deterministic business rules.
        Returns (is_approved, reason).
        """
        # 1. Is the case active?
        current_state = CaseState(case.state)
        if current_state in {
            CaseState.RECOVERED, CaseState.MAX_ATTEMPTS, CaseState.EXPIRED,
            CaseState.CUSTOMER_DECLINED, CaseState.DISPUTED, CaseState.CANCELLED,
            CaseState.ESCALATED
        }:
            return False, f"Case is in terminal state: {current_state.value}"

        # 2. Has the payment already succeeded?
        if case.payment.status == PaymentStatus.CAPTURED:
            return False, "Payment has already succeeded"

        # 3. Has the customer opted out?
        if case.customer.opted_out:
            return False, "Customer has opted out of communications"

        # 4. Is there a dispute on this case?
        if case.disputed:
            return False, "Case is disputed by customer"

        # 5. Has max retry limit been reached?
        # Check this for retry or schedule retry actions
        if action_type in {ActionType.RETRY_PAYMENT, ActionType.SCHEDULE_RETRY}:
            if case.attempt_count >= case.max_attempts:
                return False, f"Maximum retry attempts reached ({case.attempt_count}/{case.max_attempts})"

        # 6. Idempotency Check (Duplicate Execution Protection)
        if action_id:
            action = db.query(RecoveryAction).filter(RecoveryAction.id == action_id).first()
            if action and action.status in {"success", "executing"}:
                return False, f"Action {action_id} has already been executed or is currently executing"

        # 7. Spacing of notifications (Spam Prevention)
        if action_type == ActionType.SEND_NOTIFICATION:
            # Count notifications
            notification_count = db.query(RecoveryAction).filter(
                RecoveryAction.case_id == case.id,
                RecoveryAction.action_type == ActionType.SEND_NOTIFICATION.value,
                RecoveryAction.status == "success"
            ).count()

            if notification_count >= settings.MAX_NOTIFICATIONS_PER_CASE:
                return False, f"Maximum notifications limit reached ({settings.MAX_NOTIFICATIONS_PER_CASE})"

            # Spacing check
            last_notification = db.query(RecoveryAction).filter(
                RecoveryAction.case_id == case.id,
                RecoveryAction.action_type == ActionType.SEND_NOTIFICATION.value,
                RecoveryAction.status == "success"
            ).order_by(RecoveryAction.executed_at.desc()).first()

            if last_notification and last_notification.executed_at:
                time_elapsed = datetime.datetime.utcnow() - last_notification.executed_at
                min_spacing = datetime.timedelta(hours=settings.MIN_HOURS_BETWEEN_NOTIFICATIONS)
                if time_elapsed < min_spacing:
                    hours_left = (min_spacing - time_elapsed).total_seconds() / 3600.0
                    return False, f"Notification too soon. Wait another {hours_left:.2f} hours"

        return True, "APPROVED"
