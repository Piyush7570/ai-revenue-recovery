import datetime
import uuid
from sqlalchemy.orm import Session
from app.models import AuditEvent

class AuditService:
    @staticmethod
    def log_event(
        db: Session,
        case_id: str,
        event_type: str,
        original_error: str = None,
        agent_diagnosis: str = None,
        intervention_chosen: str = None,
        action_payload: dict = None,
        result_status: str = None,
        metadata: dict = None
    ) -> AuditEvent:
        """
        Creates and stores an audit event for a given recovery case.
        """
        event = AuditEvent(
            id=f"evt_{uuid.uuid4().hex[:12]}",
            case_id=case_id,
            timestamp=datetime.datetime.utcnow(),
            event_type=event_type,
            original_error=original_error,
            agent_diagnosis=agent_diagnosis,
            intervention_chosen=intervention_chosen,
            action_payload=action_payload,
            result_status=result_status,
            metadata_json=metadata
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event
