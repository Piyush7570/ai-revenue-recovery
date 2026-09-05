import datetime
from sqlalchemy.orm import Session
from app.models import RecoveryCase
from app.services.audit import AuditService
from app.schemas import CaseState

class StateMachine:
    # Terminal states (once reached, no further transitions are allowed)
    TERMINAL_STATES = {
        CaseState.RECOVERED,
        CaseState.MAX_ATTEMPTS,
        CaseState.EXPIRED,
        CaseState.CUSTOMER_DECLINED,
        CaseState.DISPUTED,
        CaseState.CANCELLED,
        CaseState.ESCALATED
    }

    # Standard allowable transitions
    # Format: current_state -> set of next states
    ALLOWED_TRANSITIONS = {
        CaseState.PAYMENT_FAILED: {CaseState.DIAGNOSING, CaseState.CANCELLED},
        CaseState.DIAGNOSING: {CaseState.RECOVERY_PLANNED, CaseState.CANCELLED, CaseState.ESCALATED},
        CaseState.RECOVERY_PLANNED: {CaseState.ACTION_PENDING, CaseState.CANCELLED, CaseState.ESCALATED, CaseState.RECOVERED},
        CaseState.ACTION_PENDING: {CaseState.WAITING, CaseState.RECOVERED, CaseState.MAX_ATTEMPTS, CaseState.EXPIRED, CaseState.CUSTOMER_DECLINED, CaseState.DISPUTED, CaseState.CANCELLED, CaseState.ESCALATED},
        CaseState.WAITING: {CaseState.ACTION_PENDING, CaseState.DIAGNOSING, CaseState.RECOVERED, CaseState.MAX_ATTEMPTS, CaseState.EXPIRED, CaseState.CUSTOMER_DECLINED, CaseState.DISPUTED, CaseState.CANCELLED, CaseState.ESCALATED}
    }

    @classmethod
    def is_valid_transition(cls, from_state: CaseState, to_state: CaseState) -> bool:
        """
        Validates if a transition from from_state to to_state is allowed.
        """
        # Self transitions are always permitted
        if from_state == to_state:
            return True

        # Terminal states are absolute dead-ends
        if from_state in cls.TERMINAL_STATES:
            return False

        # Any active state is allowed to jump to these terminal/safety states
        GLOBAL_TERMINALS = {
            CaseState.RECOVERED, 
            CaseState.DISPUTED, 
            CaseState.CANCELLED, 
            CaseState.CUSTOMER_DECLINED,
            CaseState.ESCALATED
        }
        if to_state in GLOBAL_TERMINALS:
            return True

        # Check explicit transitions
        allowed = cls.ALLOWED_TRANSITIONS.get(from_state, set())
        return to_state in allowed

    @classmethod
    def transition_to(
        cls,
        db: Session,
        case: RecoveryCase,
        new_state: CaseState,
        reason: str = None,
        metadata: dict = None
    ) -> RecoveryCase:
        """
        Transitions the recovery case to a new state.
        Raises ValueError if transition is invalid.
        """
        current_state = CaseState(case.state)
        new_state = CaseState(new_state)

        if not cls.is_valid_transition(current_state, new_state):
            error_msg = f"Invalid state transition: {current_state.value} -> {new_state.value}"
            AuditService.log_event(
                db=db,
                case_id=case.id,
                event_type="INVALID_TRANSITION_ATTEMPTED",
                original_error=error_msg,
                metadata={"from_state": current_state.value, "to_state": new_state.value}
            )
            raise ValueError(error_msg)

        # Update case state
        case.state = new_state.value
        case.updated_at = datetime.datetime.utcnow()

        # If entering a terminal state, set closed_at
        if new_state in cls.TERMINAL_STATES:
            case.closed_at = datetime.datetime.utcnow()
            
            # If recovered, ensure payment status is updated as well
            if new_state == CaseState.RECOVERED:
                case.payment.status = "captured"
                case.payment.updated_at = datetime.datetime.utcnow()

        db.commit()
        db.refresh(case)

        # Log transition in Audit Trail
        AuditService.log_event(
            db=db,
            case_id=case.id,
            event_type=f"STATE_CHANGED",
            metadata={
                "from_state": current_state.value,
                "to_state": new_state.value,
                "reason": reason,
                **(metadata or {})
            }
        )

        return case
