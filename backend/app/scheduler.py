import time
import datetime
import threading
from abc import ABC, abstractmethod
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import RecoveryAction, RecoveryCase
from app.schemas import ActionStatus, ActionType, CaseState

class BaseScheduler(ABC):
    @abstractmethod
    def schedule_action(self, db: Session, case_id: str, action_type: ActionType, scheduled_at: datetime.datetime, payload: dict = None) -> str:
        """
        Schedules a recovery action to run at a specific time.
        """
        pass

    @abstractmethod
    def cancel_pending_actions(self, db: Session, case_id: str) -> int:
        """
        Cancels all pending scheduled actions for a given case.
        Returns the number of cancelled actions.
        """
        pass

class InMemoryScheduler(BaseScheduler):
    def __init__(self):
        self._running = False
        self._thread = None
        self.lock = threading.Lock()

    def schedule_action(self, db: Session, case_id: str, action_type: ActionType, scheduled_at: datetime.datetime, payload: dict = None) -> str:
        import uuid
        action_id = f"act_{uuid.uuid4().hex[:12]}"
        
        # Save scheduled action to database
        action = RecoveryAction(
            id=action_id,
            case_id=case_id,
            action_type=action_type.value,
            status=ActionStatus.SCHEDULED.value,
            scheduled_at=scheduled_at,
            payload=payload
        )
        db.add(action)
        db.commit()
        
        # Also update next_action on case
        case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
        if case:
            case.next_action = action_type.value
            case.next_action_at = scheduled_at
            db.commit()
            
        return action_id

    def cancel_pending_actions(self, db: Session, case_id: str) -> int:
        """
        Finds all scheduled actions for a case and changes status to 'failed' or deletes them.
        We will change their status to 'failed' with reason 'Cancelled by system' to keep the audit trail.
        """
        scheduled_actions = db.query(RecoveryAction).filter(
            RecoveryAction.case_id == case_id,
            RecoveryAction.status == ActionStatus.SCHEDULED.value
        ).all()
        
        count = 0
        for act in scheduled_actions:
            act.status = ActionStatus.FAILED.value
            act.failure_reason = "Cancelled (Payment recovered or case closed)"
            act.executed_at = datetime.datetime.utcnow()
            count += 1
            
        # Clear next action in case
        case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
        if case:
            case.next_action = None
            case.next_action_at = None
            
        db.commit()
        return count

    def start(self, run_interval_seconds: int = 2):
        """
        Starts the background worker thread.
        """
        with self.lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(
                target=self._run_loop,
                args=(run_interval_seconds,),
                daemon=True,
                name="SchedulerDaemon"
            )
            self._thread.start()

    def stop(self):
        """
        Stops the background worker thread.
        """
        with self.lock:
            self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _run_loop(self, interval: int):
        while True:
            with self.lock:
                if not self._running:
                    break
            
            try:
                self._check_and_execute_actions()
            except Exception as e:
                # Silently catch/log error in daemon thread to avoid crashing the scheduler loop
                print(f"[SchedulerDaemon Error]: {e}", flush=True)
                
            time.sleep(interval)

    def _check_and_execute_actions(self):
        """
        Queries database for due scheduled actions and executes them.
        """
        db = SessionLocal()
        try:
            now = datetime.datetime.utcnow()
            # Fetch actions that are due
            due_actions = db.query(RecoveryAction).filter(
                RecoveryAction.status == ActionStatus.SCHEDULED.value,
                RecoveryAction.scheduled_at <= now
            ).all()

            if not due_actions:
                return

            from app.action_executor import ActionExecutor
            for action in due_actions:
                # Execute in separate context
                try:
                    ActionExecutor.execute_action(db, action.id)
                except Exception as e:
                    print(f"Error executing action {action.id}: {e}", flush=True)
        finally:
            db.close()

# Global scheduler instance
scheduler = InMemoryScheduler()
