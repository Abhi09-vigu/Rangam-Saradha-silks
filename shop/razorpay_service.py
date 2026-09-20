import hmac
import hashlib
import logging
from decimal import Decimal
from django.conf import settings
import razorpay
from razorpay.errors import SignatureVerificationError

logger = logging.getLogger(__name__)


def get_razorpay_client():
    """
    Initializes and returns the Razorpay client using backend settings.
    Never exposes RAZORPAY_KEY_SECRET to frontend.
    Dynamically loads/refreshes from .env if needed.
    """
    key_id = getattr(settings, 'RAZORPAY_KEY_ID', '') or os.environ.get('RAZORPAY_KEY_ID', '')
    key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '') or os.environ.get('RAZORPAY_KEY_SECRET', '')

    if not key_id or not key_secret or 'placeholder' in key_id or 'placeholder' in key_secret:
        try:
            from dotenv import load_dotenv
            load_dotenv(settings.BASE_DIR / ".env", override=True)
            key_id = os.environ.get('RAZORPAY_KEY_ID', '')
            key_secret = os.environ.get('RAZORPAY_KEY_SECRET', '')
            settings.RAZORPAY_KEY_ID = key_id
            settings.RAZORPAY_KEY_SECRET = key_secret
        except Exception as e:
            logger.error(f"Error reloading .env for Razorpay keys: {e}")

    if not key_id or not key_secret:
        logger.error("Razorpay API keys are not configured in settings/environment.")
    return razorpay.Client(auth=(key_id, key_secret))


def create_razorpay_order(amount_in_inr, receipt, notes=None):
    """
    Creates an official Razorpay Order.
    Amount is converted to paise (1 INR = 100 paise) as an integer.
    """
    client = get_razorpay_client()
    amount_decimal = Decimal(str(amount_in_inr))
    amount_in_paise = int(round(amount_decimal * 100))

    data = {
        "amount": amount_in_paise,
        "currency": "INR",
        "receipt": str(receipt),
        "payment_capture": 1
    }
    if notes and isinstance(notes, dict):
        data["notes"] = notes

    logger.info(f"Creating Razorpay order for receipt={receipt}, amount={amount_in_paise} paise")
    razorpay_order = client.order.create(data=data)
    return razorpay_order


def verify_payment_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
    """
    Verifies Razorpay HMAC SHA256 signature using the official SDK utility.
    Returns True if valid, False otherwise.
    """
    if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
        logger.warning("Missing parameters for Razorpay signature verification.")
        return False

    client = get_razorpay_client()
    params_dict = {
        'razorpay_order_id': razorpay_order_id,
        'razorpay_payment_id': razorpay_payment_id,
        'razorpay_signature': razorpay_signature
    }

    try:
        client.utility.verify_payment_signature(params_dict)
        logger.info(f"Razorpay signature verified successfully for order {razorpay_order_id}")
        return True
    except SignatureVerificationError as e:
        logger.warning(f"Razorpay SignatureVerificationError for order {razorpay_order_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during Razorpay signature verification: {e}")
        # Fallback to direct HMAC SHA256 comparison
        try:
            key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')
            msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode('utf-8')
            generated_signature = hmac.new(key_secret.encode('utf-8'), msg, hashlib.sha256).hexdigest()
            return hmac.compare_digest(generated_signature, razorpay_signature)
        except Exception as inner_e:
            logger.error(f"HMAC fallback verification failed: {inner_e}")
            return False
