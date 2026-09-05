import hmac
import hashlib
import base64
import httpx
from app.providers.base import BasePaymentProvider
from app.config import settings

class RazorpayProvider(BasePaymentProvider):
    def __init__(self):
        self.key_id = settings.RAZORPAY_KEY_ID
        self.key_secret = settings.RAZORPAY_KEY_SECRET
        self.webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
        
        # Build basic auth header
        auth_str = f"{self.key_id}:{self.key_secret}"
        auth_bytes = auth_str.encode("utf-8")
        self.auth_header = f"Basic {base64.b64encode(auth_bytes).decode('utf-8')}"
        self.base_url = "https://api.razorpay.com/v1"

    def get_payment(self, payment_id: str) -> dict:
        """
        Retrieves details of a payment from Razorpay API.
        """
        with httpx.Client() as client:
            response = client.get(
                f"{self.base_url}/payments/{payment_id}",
                headers={"Authorization": self.auth_header}
            )
            response.raise_for_status()
            return response.json()

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
        Creates a recovery payment link via Razorpay API.
        """
        payload = {
            "amount": int(amount * 100),  # in paise
            "currency": "INR",
            "accept_partial": False,
            "description": description,
            "customer": {
                "name": customer_name,
                "email": customer_email,
                "contact": customer_phone
            },
            "notify": {
                "sms": True,
                "email": True
            },
            "reminder_enable": True,
            "notes": {
                "internal_payment_id": payment_id
            }
        }
        with httpx.Client() as client:
            response = client.post(
                f"{self.base_url}/payment_links",
                json=payload,
                headers={"Authorization": self.auth_header}
            )
            response.raise_for_status()
            res_data = response.json()
            return {
                "id": res_data.get("id"),
                "short_url": res_data.get("short_url"),
                "status": res_data.get("status"),
                "amount": amount,
                "currency": "INR",
                "payment_id": payment_id
            }

    def charge_saved_card(self, payment_id: str, amount: float) -> dict:
        """
        Tokenized payment retry using recurring charge flow on Razorpay.
        Placeholder implementation calling Razorpay API if token is configured.
        """
        # Tokenized recurring payments require token ID which is passed during payment creation.
        # This calls Razorpay's recurring API, or falls back to an exception.
        raise NotImplementedError("Recurring token charging requires direct agreement token storage.")

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """
        Verifies that a webhook request was sent by Razorpay.
        """
        if not self.webhook_secret:
            return False
        
        expected = hmac.new(
            self.webhook_secret.encode("utf-8"),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)

    def parse_webhook(self, payload: dict) -> dict:
        """
        Parses a standard Razorpay webhook payload.
        """
        event_id = payload.get("id")
        event_type = payload.get("event")
        
        entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        
        payment_id = entity.get("notes", {}).get("internal_payment_id") or entity.get("id")
        rzp_payment_id = entity.get("id")
        amount = entity.get("amount", 0) / 100.0
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
