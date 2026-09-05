from app.providers.base import BasePaymentProvider
from app.providers.razorpay import RazorpayProvider
from app.providers.simulation import SimulationProvider
from app.config import settings

def get_payment_provider() -> BasePaymentProvider:
    """
    Returns either RazorpayProvider or SimulationProvider depending on configuration.
    """
    if settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
        return RazorpayProvider()
    return SimulationProvider()
