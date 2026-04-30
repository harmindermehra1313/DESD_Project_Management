from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from ..forms import AccountDetailsForm, AddressForm, ProfilePasswordChangeForm
from ..models import Address


def get_profile_account_type_label(user):
    """
    Return the account type label shown on the profile page.

    Producers display as Producer.
    Customers display their organisation type when available:
    Individual, Business, or Community Group.
    """

    if user.role == "PRODUCER":
        return "Producer"

    customer_profile = getattr(user, "customer_profile", None)

    if customer_profile and customer_profile.organisation_type:
        return customer_profile.organisation_type

    return user.get_role_display() or user.role


@login_required
def profile(request):
    """
    Display and update the logged-in user's profile details.

    Supported updates:
    - name and phone number
    - default delivery and billing address
    - password change after validating the current password
    """

    user = request.user

    address = (
        Address.objects
        .filter(user=user, is_default_delivery=True)
        .first()
        or Address.objects.filter(user=user).first()
    )

    account_form = AccountDetailsForm(user=user)
    address_form = AddressForm(instance=address)
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

        elif form_type == "address":
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

    context = {
        "account_form": account_form,
        "address_form": address_form,
        "password_form": password_form,
        "profile_account_type": get_profile_account_type_label(user),
    }

    return render(request, "accounts/profile.html", context)