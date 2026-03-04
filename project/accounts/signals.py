# accounts/signals.py
from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from carts.services import cart_merge_guest_into_user
from carts.models import Cart


@receiver(user_logged_in)
def merge_guest_cart_on_login(sender, request, user, **kwargs):
    guest_session_key = request.COOKIES.get(settings.SESSION_COOKIE_NAME)
    if not guest_session_key:
        return

    if not Cart.objects.filter(session_key=guest_session_key, status="ACTIVE").exists():
        return

    cart_merge_guest_into_user(session_key=guest_session_key, user_id=user.id)