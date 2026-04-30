# docker compose exec -e DEBUG_EMAIL=jane.smith@bristolvalleyfarm.com -e DEBUG_PASSWORD=aaAA1111@ web python manage.py shell -c "exec(open('accounts/tests/debug/debug_registered_account.py').read())"
"""
Debug registered account data after manual registration.

Run example:
docker compose exec \
  -e DEBUG_EMAIL=jane.smith@bristolvalleyfarm.com \
  -e DEBUG_PASSWORD=ProducerTest@123 \
  web python manage.py shell -c "exec(open('accounts/tests/debug/debug_registered_account.py').read())"

Purpose:
- confirm the User row exists
- confirm role is PRODUCER/CUSTOMER
- confirm password is stored as a Django hash, not plain text
- confirm check_password() works when DEBUG_PASSWORD is supplied
- print related Producer/Customer profile data
- print saved Address rows, if any
"""

import os
from pprint import pprint

from django.contrib.auth import get_user_model

try:
    from accounts.models import Address, Customer, Producer
except ImportError as exc:
    raise ImportError(
        "Could not import Address, Customer, and Producer from accounts.models. "
        "Check model names in accounts/models.py."
    ) from exc


SENSITIVE_FIELD_NAMES = {
    "password",
    "bank_account_number",
    "bank_sort_code",
    "paypal_email",
}

PROFILE_RELATION_NAMES = [
    "producer_profile",
    "customer_profile",
    "profile",
]


def print_section(title):
    print("\n" + title)
    print("-" * 100)


def mask_value(field_name, value):
    if value in (None, ""):
        return value

    value = str(value)

    if field_name == "password":
        algorithm = value.split("$", 1)[0] if "$" in value else "unknown"
        return {
            "algorithm": algorithm,
            "stored_value_preview": value[:20] + "...",
            "stored_value_length": len(value),
        }

    if field_name in SENSITIVE_FIELD_NAMES:
        return "***MASKED***"

    return value


def model_to_simple_dict(obj):
    if not obj:
        return {}

    data = {}

    for field in obj._meta.fields:
        value = getattr(obj, field.name, None)

        if field.is_relation and value is not None:
            data[field.name] = {
                "id": getattr(value, "pk", None),
                "value": str(value),
            }
        else:
            data[field.name] = mask_value(field.name, value)

    return data


def get_debug_email():
    email = os.environ.get("DEBUG_EMAIL", "").strip().lower()

    if not email:
        raise ValueError(
            "DEBUG_EMAIL is required. Example: "
            "-e DEBUG_EMAIL=jane.smith@bristolvalleyfarm.com"
        )

    return email


def get_user_by_email(email):
    User = get_user_model()
    return User.objects.filter(email__iexact=email).first()


def print_user_summary(user):
    print_section("USER ROW")
    print("User found:", bool(user))

    if not user:
        return

    print("ID:", user.pk)
    print("Email:", getattr(user, "email", None))
    print("Name:", getattr(user, "name", None))
    print("Phone:", getattr(user, "phone", None))
    print("Role:", getattr(user, "role", None))
    print("Is active:", getattr(user, "is_active", None))
    print("Is staff:", getattr(user, "is_staff", None))
    print("Is superuser:", getattr(user, "is_superuser", None))

    stored_password = getattr(user, "password", "")
    print("Password stored as plain text:", stored_password == os.environ.get("DEBUG_PASSWORD", ""))
    print("Password hash algorithm:", stored_password.split("$", 1)[0] if "$" in stored_password else "unknown")

    debug_password = os.environ.get("DEBUG_PASSWORD")
    if debug_password:
        print("check_password(DEBUG_PASSWORD):", user.check_password(debug_password))
    else:
        print("check_password(DEBUG_PASSWORD): not checked because DEBUG_PASSWORD was not supplied")

    print("\nAll direct User fields:")
    pprint(model_to_simple_dict(user), width=120)


def print_related_profiles(user):
    print_section("RELATED PROFILE ROWS")

    found_profile = False

    for relation_name in PROFILE_RELATION_NAMES:
        try:
            profile = getattr(user, relation_name, None)
        except Exception:
            profile = None

        if not profile:
            continue

        found_profile = True
        print(f"\nRelation: {relation_name}")
        print("Profile model:", profile.__class__.__name__)
        print("Profile ID:", profile.pk)
        print("Profile string:", str(profile))
        pprint(model_to_simple_dict(profile), width=120)

    if not found_profile:
        print("No profile relation found using:", PROFILE_RELATION_NAMES)


def print_direct_model_lookup(user):
    print_section("DIRECT PRODUCER / CUSTOMER LOOKUP")

    producer = Producer.objects.filter(user=user).first()
    customer = Customer.objects.filter(user=user).first()

    print("Producer row exists:", bool(producer))
    if producer:
        print("Producer ID:", producer.pk)
        print("Farm name:", getattr(producer, "farm_name", None))
        print("Farm postcode:", getattr(producer, "farm_postcode", None))
        print("Contact email:", getattr(producer, "contact_email", None))
        print("Contact phone:", getattr(producer, "contact_phone", None))
        print("Payout method:", getattr(producer, "payout_method", None))
        print("\nAll direct Producer fields:")
        pprint(model_to_simple_dict(producer), width=120)

    print("\nCustomer row exists:", bool(customer))
    if customer:
        print("Customer ID:", customer.pk)
        print("Organisation type:", getattr(customer, "organisation_type", None))
        print("Contact person:", getattr(customer, "contact_person_name", None))
        print("\nAll direct Customer fields:")
        pprint(model_to_simple_dict(customer), width=120)


def print_addresses(user):
    print_section("ADDRESS ROWS")

    addresses = list(Address.objects.filter(user=user).order_by("id"))

    print("Address count:", len(addresses))

    if not addresses:
        print("No Address rows found for this user.")
        print("For producer registration, this may be expected if farm address/postcode is stored on Producer.")
        return

    for address in addresses:
        print(f"\nAddress ID: {address.pk}")
        pprint(model_to_simple_dict(address), width=120)


def print_final_manual_test_result(user):
    print_section("MANUAL TEST EVIDENCE SUMMARY")

    if not user:
        print("FAIL: No User row found for DEBUG_EMAIL.")
        return

    role = getattr(user, "role", None)
    producer = Producer.objects.filter(user=user).first()
    password_is_hashed = getattr(user, "password", "") != os.environ.get("DEBUG_PASSWORD", "")

    print("Account created:", True)
    print("Email saved:", getattr(user, "email", None))
    print("Role saved:", role)
    print("Producer profile exists:", bool(producer))
    print("Password appears hashed:", password_is_hashed)

    if role == "PRODUCER" and producer and password_is_hashed:
        print("Suggested TC-001 backend evidence status: PASS")
    else:
        print("Suggested TC-001 backend evidence status: CHECK OUTPUT ABOVE")


def main():
    email = get_debug_email()
    user = get_user_by_email(email)

    print_section("DEBUG INPUT")
    print("DEBUG_EMAIL:", email)
    print("DEBUG_PASSWORD supplied:", bool(os.environ.get("DEBUG_PASSWORD")))

    print_user_summary(user)

    if not user:
        return

    print_related_profiles(user)
    print_direct_model_lookup(user)
    print_addresses(user)
    print_final_manual_test_result(user)


main()