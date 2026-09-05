import datetime
from sqlalchemy.orm import Session
from app.models import RecoveryAction, RecoveryCase, Payment
from app.schemas import ActionStatus, ActionType, CaseState, PaymentStatus
from app.policy_engine import PolicyEngine
from app.state_machine import StateMachine
from app.providers import get_payment_provider
from app.services.audit import AuditService

class ActionExecutor:
    @staticmethod
    def execute_action(db: Session, action_id: str) -> None:
        """
        Executes a scheduled recovery action. Validates via policy engine first.
        Protects against race conditions by re-querying and re-validating state.
        """
        action = db.query(RecoveryAction).filter(RecoveryAction.id == action_id).first()
        if not action:
            return

        # Double check status (must be scheduled)
        if action.status != ActionStatus.SCHEDULED.value:
            return

        case = db.query(RecoveryCase).filter(RecoveryCase.id == action.case_id).first()
        if not case:
            action.status = ActionStatus.FAILED.value
            action.failure_reason = "Parent recovery case not found"
            db.commit()
            return

        # 1. Race Condition / Safety validation via PolicyEngine
        action_type = ActionType(action.action_type)
        is_approved, reason = PolicyEngine.validate_action(db, case, action_type, action_id)

        if not is_approved:
            # Action is rejected by safety engine
            action.status = ActionStatus.FAILED.value
            action.failure_reason = f"Safety Policy Rejected: {reason}"
            action.executed_at = datetime.datetime.utcnow()
            db.commit()

            # Audit rejection
            AuditService.log_event(
                db=db,
                case_id=case.id,
                event_type="POLICY_REJECTED",
                intervention_chosen=action.action_type,
                metadata={"reason": reason, "action_id": action.id}
            )

            # Auto-transition case to terminal states if appropriate
            if "Maximum retry attempts" in reason:
                StateMachine.transition_to(
                    db, case, CaseState.MAX_ATTEMPTS, 
                    reason="Safety policy auto-closed case: Max retry limits reached"
                )
            elif "opted out" in reason:
                StateMachine.transition_to(
                    db, case, CaseState.CANCELLED,
                    reason="Safety policy auto-cancelled case: Customer opted out"
                )
            elif "disputed" in reason:
                StateMachine.transition_to(
                    db, case, CaseState.DISPUTED,
                    reason="Safety policy auto-closed case: Customer raised a dispute"
                )
            elif "already succeeded" in reason:
                StateMachine.transition_to(
                    db, case, CaseState.RECOVERED,
                    reason="Safety policy auto-closed case: Payment already captured"
                )
            return

        # 2. Safety Approved: Enter ACTION_PENDING state
        StateMachine.transition_to(
            db=db,
            case=case,
            new_state=CaseState.ACTION_PENDING,
            reason=f"Safety engine approved execution of {action_type.value}"
        )
        
        # Log policy approval in audit trail
        AuditService.log_event(
            db=db,
            case_id=case.id,
            event_type="POLICY_APPROVED",
            intervention_chosen=action.action_type,
            metadata={"action_id": action.id}
        )

        action.status = ActionStatus.EXECUTING.value
        db.commit()

        provider = get_payment_provider()

        try:
            if action_type == ActionType.RETRY_PAYMENT:
                # Increment attempts immediately
                case.attempt_count += 1
                db.commit()

                # Execute retry charge
                result = provider.charge_saved_card(case.payment.id, case.payment.amount)
                
                # If successful
                action.status = ActionStatus.SUCCESS.value
                action.result = result
                action.executed_at = datetime.datetime.utcnow()
                db.commit()

                AuditService.log_event(
                    db=db,
                    case_id=case.id,
                    event_type="PAYMENT_CAPTURED",
                    action_payload=action.payload,
                    result_status="success",
                    metadata={"provider_result": result}
                )

                # Transition to RECOVERED (terminal state)
                StateMachine.transition_to(
                    db=db,
                    case=case,
                    new_state=CaseState.RECOVERED,
                    reason=f"Saved card retry succeeded! Charged {case.payment.amount} INR"
                )

            elif action_type == ActionType.CREATE_PAYMENT_LINK:
                # Create recovery link
                desc = f"Recovery Link for Payment Failure (Ref: {case.payment.id})"
                result = provider.create_payment_link(
                    payment_id=case.payment.id,
                    amount=case.payment.amount,
                    customer_name=case.customer.name,
                    customer_email=case.customer.email,
                    customer_phone=case.customer.phone,
                    description=desc
                )

                action.status = ActionStatus.SUCCESS.value
                action.result = result
                action.executed_at = datetime.datetime.utcnow()
                db.commit()

                # Audit link creation
                AuditService.log_event(
                    db=db,
                    case_id=case.id,
                    event_type="PAYMENT_LINK_CREATED",
                    action_payload=action.payload,
                    result_status="success",
                    metadata={"payment_link_url": result.get("short_url")}
                )

                # Auto-schedule simulated notification
                # We can notify immediately
                AuditService.log_event(
                    db=db,
                    case_id=case.id,
                    event_type="NOTIFICATION_SENT",
                    metadata={
                        "channel": case.customer.preferred_channel,
                        "recipient": case.customer.email if case.customer.preferred_channel == "EMAIL" else case.customer.phone,
                        "message": f"Hi {case.customer.name}, we couldn't process your payment. Pay here: {result.get('short_url')}"
                    }
                )

                # Transition to WAITING (waiting for user payment)
                StateMachine.transition_to(
                    db=db,
                    case=case,
                    new_state=CaseState.WAITING,
                    reason="Payment link sent to customer. Waiting for transaction callback."
                )

            elif action_type == ActionType.SEND_NOTIFICATION:
                # Direct recovery message simulation
                # Log success immediately
                action.status = ActionStatus.SUCCESS.value
                action.executed_at = datetime.datetime.utcnow()
                db.commit()

                AuditService.log_event(
                    db=db,
                    case_id=case.id,
                    event_type="NOTIFICATION_SENT",
                    metadata={
                        "channel": case.customer.preferred_channel,
                        "recipient": case.customer.email if case.customer.preferred_channel == "EMAIL" else case.customer.phone,
                        "message": action.payload.get("message", f"Hi {case.customer.name}, please complete your payment of {case.payment.amount} INR.")
                    }
                )

                StateMachine.transition_to(
                    db=db,
                    case=case,
                    new_state=CaseState.WAITING,
                    reason="Recovery message delivered to customer. Waiting."
                )

            elif action_type == ActionType.ESCALATE:
                action.status = ActionStatus.SUCCESS.value
                action.executed_at = datetime.datetime.utcnow()
                db.commit()

                StateMachine.transition_to(
                    db=db,
                    case=case,
                    new_state=CaseState.ESCALATED,
                    reason="Case escalated to support/collections team."
                )

            elif action_type == ActionType.CLOSE_CASE:
                action.status = ActionStatus.SUCCESS.value
                action.executed_at = datetime.datetime.utcnow()
                db.commit()

                StateMachine.transition_to(
                    db=db,
                    case=case,
                    new_state=CaseState.CANCELLED,
                    reason="Case closed by recovery action directive."
                )

        except Exception as e:
            # Handle failure scenario gracefully (e.g. Provider is down/failed)
            # Mark action as failed, log original error, log audit, and keep case active in fallback state
            action.status = ActionStatus.FAILED.value
            action.failure_reason = str(e)
            action.executed_at = datetime.datetime.utcnow()
            db.commit()

            AuditService.log_event(
                db=db,
                case_id=case.id,
                event_type="PROVIDER_API_FAILED",
                original_error=str(e),
                intervention_chosen=action.action_type,
                metadata={"action_id": action.id}
            )

            # Move case state back to WAITING or DIAGNOSING for fallback
            # We transition back to WAITING so the system can reschedule/retry later without loops
            StateMachine.transition_to(
                db=db,
                case=case,
                new_state=CaseState.WAITING,
                reason=f"Action execution failed: {str(e)}. Case remains active for fallback strategy."
            )
            
            # If the failed action was a payment retry, check if we need to terminate on max attempts
            if action_type == ActionType.RETRY_PAYMENT and case.attempt_count >= case.max_attempts:
                StateMachine.transition_to(
                    db=db,
                    case=case,
                    new_state=CaseState.MAX_ATTEMPTS,
                    reason="Max attempts reached after failed payment charge"
                )
