from abc import ABC, abstractmethod

class BasePaymentProvider(ABC):
    @abstractmethod
    def get_payment(self, payment_id: str) -> dict:
        """
        Retrieves details of a payment from the provider.
        """
        pass

    @abstractmethod
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
        Creates a recovery payment link.
        """
        pass

    @abstractmethod
    def charge_saved_card(self, payment_id: str, amount: float) -> dict:
        """
        Attempts to charge the customer's saved payment method (tokenized retry).
        """
        pass

    @abstractmethod
    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """
        Verifies that a webhook request was sent by the provider.
        """
        pass

    @abstractmethod
    def parse_webhook(self, payload: dict) -> dict:
        """
        Parses a webhook payload into standard internal event fields:
        {
            "event_id": str,
            "event_type": str, # e.g. "payment.captured", "payment.failed"
            "payment_id": str,
            "razorpay_payment_id": str,
            "amount": float,
            "status": str,
            "failure_code": str,
            "failure_description": str
        }
        """
        pass
