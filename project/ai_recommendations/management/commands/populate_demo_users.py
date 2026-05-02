# docker compose exec web python manage.py populate_demo_users --clear --count 100
# docker compose exec web python manage.py populate_demo_users --clear --count 100 --firebase
# docker compose exec web python manage.py populate_demo_users --clear --count 200 --firebase

"""
Populate demo customer users.

Creates a mixed set of:
- individual customer accounts
- business customer accounts
- community group customer accounts

Generated account format:
- name: User 1, User 2, User 3...
- email: user1@gmail.com, user2@gmail.com, user3@gmail.com...
- password: customerpass

By default, this command creates Django users only.

Use --firebase to also create or update matching Firebase Authentication
users. This is useful when the login page uses Firebase authentication.
"""

import re

import firebase_admin
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from firebase_admin import auth as firebase_auth

from accounts.models import Address, Customer, User


ACCOUNT_TYPES = [
    "INDIVIDUAL",
    "BUSINESS",
    "COMMUNITY_GROUP",
]


UK_DEMO_ADDRESSES = [
    {
        "line1": "10 Park Street",
        "line2": "",
        "city": "Bristol",
        "postcode": "BS1 5TY",
    },
    {
        "line1": "22 Gloucester Road",
        "line2": "",
        "city": "Bristol",
        "postcode": "BS7 8AE",
    },
    {
        "line1": "35 Whiteladies Road",
        "line2": "",
        "city": "Bristol",
        "postcode": "BS8 2LS",
    },
    {
        "line1": "48 North Street",
        "line2": "",
        "city": "Bristol",
        "postcode": "BS3 1HJ",
    },
    {
        "line1": "61 Stokes Croft",
        "line2": "",
        "city": "Bristol",
        "postcode": "BS1 3QY",
    },
    {
        "line1": "74 Baldwin Street",
        "line2": "",
        "city": "Bristol",
        "postcode": "BS1 1QZ",
    },
    {
        "line1": "87 Redland Road",
        "line2": "",
        "city": "Bristol",
        "postcode": "BS6 6YE",
    },
    {
        "line1": "96 Stapleton Road",
        "line2": "",
        "city": "Bristol",
        "postcode": "BS5 0QX",
    },
    {
        "line1": "108 Fishponds Road",
        "line2": "",
        "city": "Bristol",
        "postcode": "BS5 6SA",
    },
    {
        "line1": "120 Bedminster Road",
        "line2": "",
        "city": "Bristol",
        "postcode": "BS3 5NP",
    },
]


BUSINESS_NAMES = [
    "Bristol Green Café",
    "Harbourside Grocers",
    "Clifton Catering Co",
    "Easton Fresh Foods",
    "Redland Restaurant",
    "Southville Bakery",
    "Stapleton Kitchen",
    "Avon Valley Deli",
    "Temple Market Foods",
    "Bedminster Bistro",
]


COMMUNITY_NAMES = [
    "Bristol Food Share",
    "Easton Community Kitchen",
    "Southville Pantry",
    "Avon Mutual Aid Group",
    "Redland Community Hub",
    "St Pauls Food Project",
    "Knowle Community Table",
    "Fishponds Support Group",
    "Clifton Neighbourhood Kitchen",
    "Bedminster Food Collective",
]


def build_uk_mobile(number, block):
    """
    Return a format-valid UK mobile number.

    Format:
    +44 7700 XXX XXX

    Example:
    +447700100001
    """
    return f"+447700{block + number:06d}"


def get_demo_address(offset):
    """
    Return a reusable Bristol-format demo address.
    """
    return UK_DEMO_ADDRESSES[offset % len(UK_DEMO_ADDRESSES)]


class Command(BaseCommand):
    help = "Create mixed demo customer users for recommender and ordering demos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=100,
            help="Number of demo users to create. Default: 100.",
        )

        parser.add_argument(
            "--password",
            type=str,
            default="customerpass",
            help="Password assigned to generated demo users.",
        )

        parser.add_argument(
            "--email-domain",
            type=str,
            default="gmail.com",
            help="Email domain for generated demo users.",
        )

        parser.add_argument(
            "--start-index",
            type=int,
            default=1,
            help="Starting number for generated demo users.",
        )

        parser.add_argument(
            "--reset-passwords",
            action="store_true",
            help="Reset passwords for existing matching Django demo users.",
        )

        parser.add_argument(
            "--clear",
            action="store_true",
            help=(
                "Delete existing generated Django demo users before creating "
                "new ones. Only users matching user<number>@<email-domain> "
                "and name='User <number>' are deleted."
            ),
        )

        parser.add_argument(
            "--firebase",
            action="store_true",
            help=(
                "Also create or update matching Firebase Authentication users. "
                "Existing Firebase users are updated with the same password "
                "and display name."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        count = options["count"]
        password = options["password"]
        email_domain = options["email_domain"]
        start_index = options["start_index"]
        reset_passwords = options["reset_passwords"]
        clear = options["clear"]
        use_firebase = options["firebase"]

        if count <= 0:
            raise CommandError("--count must be greater than 0.")

        if start_index <= 0:
            raise CommandError("--start-index must be greater than 0.")

        if use_firebase:
            self._ensure_firebase_initialised()

        if clear:
            deleted_total, deleted_breakdown = self._clear_demo_users(
                email_domain=email_domain
            )

            self.stdout.write(
                self.style.WARNING(
                    f"Cleared existing Django demo data: "
                    f"{deleted_total} object(s) deleted."
                )
            )

            if deleted_breakdown:
                for model_name, deleted_count in deleted_breakdown.items():
                    self.stdout.write(f"- {model_name}: {deleted_count}")

        created_users = 0
        existing_users = 0
        firebase_created_users = 0
        firebase_updated_users = 0

        account_type_counts = {
            "INDIVIDUAL": 0,
            "BUSINESS": 0,
            "COMMUNITY_GROUP": 0,
        }

        for offset in range(count):
            number = start_index + offset
            account_type = ACCOUNT_TYPES[offset % len(ACCOUNT_TYPES)]

            full_name = f"User {number}"
            email = f"user{number}@{email_domain}"
            phone = build_uk_mobile(number=number, block=100000)
            address = get_demo_address(offset)

            user, user_created = User.objects.get_or_create(
                email=email,
                defaults={
                    "name": full_name,
                    "phone": phone,
                    "role": User.Role_choices.CUSTOMER,
                    "is_active": True,
                    "is_staff": False,
                },
            )

            if user_created:
                user.set_password(password)
                user.save(update_fields=["password"])
                created_users += 1
            else:
                existing_users += 1
                changed_fields = []

                if user.name != full_name:
                    user.name = full_name
                    changed_fields.append("name")

                if user.phone != phone:
                    user.phone = phone
                    changed_fields.append("phone")

                if user.role != User.Role_choices.CUSTOMER:
                    user.role = User.Role_choices.CUSTOMER
                    changed_fields.append("role")

                if not user.is_active:
                    user.is_active = True
                    changed_fields.append("is_active")

                if user.is_staff:
                    user.is_staff = False
                    changed_fields.append("is_staff")

                if reset_passwords or use_firebase:
                    user.set_password(password)
                    changed_fields.append("password")

                if changed_fields:
                    user.save(update_fields=changed_fields)

            if use_firebase:
                firebase_status = self._create_or_update_firebase_user(
                    email=email,
                    password=password,
                    display_name=full_name,
                )

                if firebase_status == "created":
                    firebase_created_users += 1
                else:
                    firebase_updated_users += 1

            customer_defaults = self._build_customer_defaults(
                account_type=account_type,
                number=number,
                offset=offset,
            )

            Customer.objects.update_or_create(
                user=user,
                defaults=customer_defaults,
            )

            Address.objects.update_or_create(
                user=user,
                is_default_delivery=True,
                is_default_billing=True,
                defaults={
                    "line1": address["line1"],
                    "line2": address["line2"],
                    "city": address["city"],
                    "postcode": address["postcode"],
                },
            )

            account_type_counts[account_type] += 1

        self.stdout.write(self.style.SUCCESS("Demo users populated successfully."))
        self.stdout.write(f"Created Django users: {created_users}")
        self.stdout.write(f"Existing Django users updated/skipped: {existing_users}")
        self.stdout.write(f"Individual customers: {account_type_counts['INDIVIDUAL']}")
        self.stdout.write(f"Business customers: {account_type_counts['BUSINESS']}")
        self.stdout.write(
            f"Community group customers: {account_type_counts['COMMUNITY_GROUP']}"
        )

        if use_firebase:
            self.stdout.write(f"Created Firebase users: {firebase_created_users}")
            self.stdout.write(f"Updated Firebase users: {firebase_updated_users}")

        self.stdout.write(f"Default password for generated users: {password}")

    def _ensure_firebase_initialised(self):
        """
        Ensure Firebase Admin SDK has been initialised.

        The Docker container should have GOOGLE_APPLICATION_CREDENTIALS pointing
        to the service-account JSON for the intended Firebase project.
        """
        try:
            firebase_admin.get_app()
        except ValueError:
            try:
                firebase_admin.initialize_app()
            except Exception as exc:
                raise CommandError(
                    "Firebase could not be initialised. Check that "
                    "GOOGLE_APPLICATION_CREDENTIALS points to the correct "
                    "service-account JSON inside the Docker container."
                ) from exc

    def _create_or_update_firebase_user(self, email, password, display_name):
        """
        Create or update a matching Firebase Authentication user.

        If the user already exists in Firebase, the password and display name
        are updated so repeated runs stay deterministic.
        """
        try:
            firebase_auth.create_user(
                email=email,
                password=password,
                display_name=display_name,
                disabled=False,
            )
            return "created"

        except firebase_auth.EmailAlreadyExistsError:
            firebase_user = firebase_auth.get_user_by_email(email)

            firebase_auth.update_user(
                firebase_user.uid,
                password=password,
                display_name=display_name,
                disabled=False,
            )

            return "updated"

    def _clear_demo_users(self, email_domain):
        """
        Delete only generated Django demo users.

        This avoids deleting every customer account. The filter targets users
        created by this command, for example:

        user1@gmail.com
        user2@gmail.com
        user100@gmail.com

        Extra safety:
        - role must be CUSTOMER
        - name must start with 'User '
        - email must match user<number>@<email-domain>

        Firebase users are not deleted here. When --firebase is used, existing
        Firebase users are updated instead.
        """
        escaped_domain = re.escape(email_domain)

        return User.objects.filter(
            email__regex=rf"^user[0-9]+@{escaped_domain}$",
            name__startswith="User ",
            role=User.Role_choices.CUSTOMER,
        ).delete()

    def _build_customer_defaults(self, account_type, number, offset):
        if account_type == "BUSINESS":
            business_name = BUSINESS_NAMES[offset % len(BUSINESS_NAMES)]

            return {
                "organisation_type": "BUSINESS",
                "registration_number": f"BUS-{number:05d}",
                "contact_person_name": f"{business_name} Contact",
                "billing_preferences": {
                    "invoice_required": True,
                    "payment_terms": "monthly",
                },
            }

        if account_type == "COMMUNITY_GROUP":
            community_name = COMMUNITY_NAMES[offset % len(COMMUNITY_NAMES)]

            return {
                "organisation_type": "COMMUNITY_GROUP",
                "registration_number": f"COM-{number:05d}",
                "contact_person_name": f"{community_name} Coordinator",
                "billing_preferences": {
                    "invoice_required": True,
                    "payment_terms": "on_delivery",
                },
            }

        return {
            "organisation_type": "INDIVIDUAL",
            "registration_number": "",
            "contact_person_name": "",
            "billing_preferences": {
                "invoice_required": False,
                "payment_terms": "card",
            },
        }