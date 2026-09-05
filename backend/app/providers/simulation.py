import uuid
import datetime
from app.providers.base import BasePaymentProvider

# Global simulation configuration flags
SIMULATION_CONFIG = {
    "outage_enabled": False,
    "notification_failure_enabled": False,
    "duplicate_webhook_enabled": False
}

class SimulationProvider(BasePaymentProvider):
    def __init__(self, simulate_outage: bool = False):
        self.simulate_outage = simulate_outage

    def get_payment(self, payment_id: str) -> dict:
        return {
            "id": payment_id,
            "status": "failed",
            "amount": 249900,  # in paise
            "currency": "INR",
            "failure_code": "INSUFFICIENT_FUNDS",
            "failure_description": "The card has insufficient funds."
        }

    def create_payment_link(
        self,
        payment_id: str,
        amount: float,
        customer_name: str,
        customer_email: str,
        customer_phone: str,
        description: str
    ) -> dict:
        """
        Simulates payment link creation. Supports deliberate API failures for specific cases.
        """
        # Trigger deliberate failure for simulation/testing (e.g. if amount is 1337 or flags are enabled)
        if amount == 1337.0 or self.simulate_outage or SIMULATION_CONFIG["outage_enabled"]:
            raise RuntimeError("Razorpay API Error: Gateway timeout creating payment link (Simulated Failure)")

        if SIMULATION_CONFIG["notification_failure_enabled"]:
            raise RuntimeError("Notification Service Error: Failed to send SMS/Email alert (Simulated Failure)")

        link_id = f"plink_{uuid.uuid4().hex[:12]}"
        return {
            "id": link_id,
            "short_url": f"https://rzp.io/i/simulated_{link_id}",
            "status": "issued",
            "amount": int(amount * 100),
            "currency": "INR",
            "payment_id": payment_id
        }

    def charge_saved_card(self, payment_id: str, amount: float) -> dict:
        """
        Simulates card charging. Supports deliberate failure for testing.
        """
        if amount == 1337.0 or self.simulate_outage or SIMULATION_CONFIG["outage_enabled"]:
            raise RuntimeError("Razorpay API Error: Transaction declined by acquiring bank (Simulated Failure)")

        return {
            "id": f"pay_{uuid.uuid4().hex[:12]}",
            "status": "captured",
            "amount": int(amount * 100),
            "currency": "INR"
        }

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """
        Webhook verification is bypassed/mocked in simulation mode.
        """
        # Always verify webhooks as true during simulation unless they have a bad signature format
        if signature == "invalid_sig":
            return False
        return True

    def parse_webhook(self, payload: dict) -> dict:
        """
        Standardizes webhook events for the simulation provider.
        """
        event_id = payload.get("id", f"evt_{uuid.uuid4().hex[:12]}")
        event_type = payload.get("event") # e.g. payment.captured or payment.failed
        
        entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        
        # Extract fields
        payment_id = entity.get("notes", {}).get("internal_payment_id") or entity.get("id")
        rzp_payment_id = entity.get("id")
        amount = entity.get("amount", 0) / 100.0  # convert from paise
        status = entity.get("status")
        
        failure_code = entity.get("error_code")
        failure_description = entity.get("error_description")

        return {
            "event_id": event_id,
            "event_type": event_type,
            "payment_id": payment_id,
            "razorpay_payment_id": rzp_payment_id,
            "amount": amount,
            "status": status,
            "failure_code": failure_code,
            "failure_description": failure_description
        }
        
    @staticmethod
    def generate_webhook_payload(
        event_type: str,
        internal_payment_id: str,
        amount: float,
        razorpay_payment_id: str = None,
        error_code: str = None,
        error_description: str = None
    ) -> dict:
        """
        Helper method to generate mock Razorpay webhook payloads.
        """
        rzp_pay_id = razorpay_payment_id or f"pay_{uuid.uuid4().hex[:12]}"
        status = "captured" if event_type == "payment.captured" else "failed"
        
        payload = {
            "id": f"evt_{uuid.uuid4().hex[:12]}",
            "entity": "event",
            "account_id": "acc_12345",
            "event": event_type,
            "created_at": int(datetime.datetime.utcnow().timestamp()),
            "payload": {
                "payment": {
                    "entity": {
                        "id": rzp_pay_id,
                        "entity": "payment",
                        "amount": int(amount * 100),
                        "currency": "INR",
                        "status": status,
                        "order_id": None,
                        "invoice_id": None,
                        "international": False,
                        "method": "card",
                        "amount_refunded": 0,
                        "refund_status": None,
                        "captured": True if status == "captured" else False,
                        "description": "Simulated Revenue Recovery Payment",
                        "card_id": "card_sim_123",
                        "bank": None,
                        "wallet": None,
                        "vpa": None,
                        "email": "simulated_customer@example.com",
                        "contact": "+919999999999",
                        "notes": {
                            "internal_payment_id": internal_payment_id
                        },
                        "fee": 49,
                        "tax": 9,
                        "error_code": error_code,
                        "error_description": error_description,
                        "created_at": int(datetime.datetime.utcnow().timestamp())
                    }
                }
            }
        }
        return payload
