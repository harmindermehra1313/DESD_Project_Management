from django.contrib.sessions.backends.db import SessionStore
import logging
logger = logging.getLogger(__name__)

def load_checkout_data_from_session(session_key: str):
    """
    Loads the checkout data saved earlier by /orders/checkout/save/.
    Returns a dict or raises KeyError if missing.
    """
    try:
        session = SessionStore(session_key=session_key)
        data = session.get("checkout_data")

        if not data:
            raise ValueError("No checkout data found in session.")

        return data
    except Exception as e:
        logger.exception("Failed to load checkout data: %s", e)
        raise