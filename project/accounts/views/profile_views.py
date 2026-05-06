from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.urls import reverse

from notifications.models import Notification
from notifications.services.notifications import NotificationService

from ..forms import (
    AccountDetailsForm,
    AddressForm,
    ProducerBusinessProfileForm,
    ProfilePasswordChangeForm,
)
from ..models import Address


NOTIFICATIONS_PER_PAGE = 5
NOTIFICATION_PAGE_PARAM = "notifications_page"


def get_profile_account_type_label(user):
    """
    Return the account type label shown on the profile page.

    Producers display as Producer.
    Customers display a user-facing organisation type label.
    """

    if user.role == "PRODUCER":
        return "Producer"

    customer_profile = getattr(user, "customer_profile", None)

    if customer_profile and customer_profile.organisation_type:
        account_type_labels = {
            "INDIVIDUAL": "Individual",
            "BUSINESS": "Business",
            "COMMUNITY_GROUP": "Community Group",
        }

        return account_type_labels.get(
            customer_profile.organisation_type,
            customer_profile.organisation_type.replace("_", " ").title(),
        )

    return user.get_role_display() or user.role


def normalise_notification_page(page_number):
    try:
        page_number = int(page_number)
    except (TypeError, ValueError):
        return 1

    return max(page_number, 1)


def redirect_to_profile_notifications(page_number=None):
    page_number = normalise_notification_page(page_number)

    return redirect(
        f"{reverse('accounts:profile')}?"
        f"{NOTIFICATION_PAGE_PARAM}={page_number}"
        f"#profile-notifications"
    )


@login_required
def profile(request):
    """
    Display and update the logged-in user's profile details.

    Supported updates:
    - customer account details
    - customer default delivery and billing address
    - producer business profile details
    - password change after validating the current password

    Producers do not use the shared Address model on this page. Producer
    business details are stored on the Producer profile instead.
    """

    user = request.user
    is_producer = user.role == "PRODUCER"
    producer_profile = getattr(user, "producer_profile", None)

    address = None
    if not is_producer:
        address = (
            Address.objects
            .filter(user=user, is_default_delivery=True)
            .first()
            or Address.objects.filter(user=user).first()
        )

    account_form = AccountDetailsForm(user=user)
    address_form = None if is_producer else AddressForm(instance=address)
    producer_business_form = (
        ProducerBusinessProfileForm(
            user=user,
            instance=producer_profile,
        )
        if is_producer and producer_profile
        else None
    )
    password_form = ProfilePasswordChangeForm(user=user)

    if request.method == "POST":
        form_type = request.POST.get("form_type")

        if form_type == "account":
            account_form = AccountDetailsForm(request.POST, user=user)

            if account_form.is_valid():
                account_form.save()
                messages.success(request, "Profile details updated successfully.")
                return redirect("accounts:profile")

            messages.error(request, "Please correct the profile details below.")

        elif form_type == "producer_business" and is_producer:
            if not producer_profile:
                messages.error(request, "Producer profile could not be found.")
                return redirect("accounts:profile")

            producer_business_form = ProducerBusinessProfileForm(
                request.POST,
                user=user,
                instance=producer_profile,
            )

            if producer_business_form.is_valid():
                producer_business_form.save()
                messages.success(request, "Producer business details updated successfully.")
                return redirect("accounts:profile")

            messages.error(request, "Please correct the producer business details below.")

        elif form_type == "address" and not is_producer:
            address_form = AddressForm(request.POST, instance=address)

            if address_form.is_valid():
                address_obj = address_form.save(commit=False)
                address_obj.user = user
                address_obj.is_default_delivery = True
                address_obj.is_default_billing = True
                address_obj.save()

                Address.objects.filter(
                    user=user,
                    is_default_delivery=True,
                ).exclude(pk=address_obj.pk).update(is_default_delivery=False)

                Address.objects.filter(
                    user=user,
                    is_default_billing=True,
                ).exclude(pk=address_obj.pk).update(is_default_billing=False)

                messages.success(request, "Address updated successfully.")
                return redirect("accounts:profile")

            messages.error(request, "Please correct the address details below.")

        elif form_type == "address" and is_producer:
            messages.error(
                request,
                "Producer business address details are managed in the business profile section.",
            )
            return redirect("accounts:profile")

        elif form_type == "password":
            password_form = ProfilePasswordChangeForm(request.POST, user=user)

            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Password changed successfully.")
                return redirect("accounts:profile")

            messages.error(request, "Please correct the password details below.")

        else:
            messages.error(request, "Invalid profile update request.")

    notifications = None
    notification_page_range = []
    notification_page_ellipsis = ""
    unread_count = 0

    if not is_producer:
        notifications_qs = Notification.objects.filter(
            user=user,
        ).order_by("-created_at")

        paginator = Paginator(notifications_qs, NOTIFICATIONS_PER_PAGE)
        page_number = request.GET.get(NOTIFICATION_PAGE_PARAM)
        notifications = paginator.get_page(page_number)

        notification_page_range = list(
            paginator.get_elided_page_range(
                number=notifications.number,
                on_each_side=1,
                on_ends=1,
            )
        )
        notification_page_ellipsis = paginator.ELLIPSIS

        unread_count = notifications_qs.filter(read_at__isnull=True).count()

    context = {
        "account_form": account_form,
        "address_form": address_form,
        "producer_business_form": producer_business_form,
        "password_form": password_form,
        "profile_account_type": get_profile_account_type_label(user),
        "is_producer_profile": is_producer,
        "notifications": notifications,
        "notification_page_range": notification_page_range,
        "notification_page_ellipsis": notification_page_ellipsis,
        "notification_page_param": NOTIFICATION_PAGE_PARAM,
        "unread_count": unread_count,
    }

    return render(request, "accounts/profile.html", context)


@login_required
def customer_mark_notification_read(request, pk):
    page = (
        request.POST.get(NOTIFICATION_PAGE_PARAM)
        or request.GET.get(NOTIFICATION_PAGE_PARAM)
        or 1
    )

    if request.method == "POST":
        note = Notification.objects.filter(pk=pk, user=request.user).first()

        if note:
            NotificationService.mark_read(note)

    return redirect_to_profile_notifications(page)


@login_required
def customer_mark_all_notifications_read(request):
    page = (
        request.POST.get(NOTIFICATION_PAGE_PARAM)
        or request.GET.get(NOTIFICATION_PAGE_PARAM)
        or 1
    )

    if request.method == "POST":
        NotificationService.mark_all_read(request.user)

    return redirect_to_profile_notifications(page)