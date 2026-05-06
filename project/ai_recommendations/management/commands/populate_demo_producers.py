# docker compose exec web python manage.py populate_demo_producers --clear --count 50
# docker compose exec web python manage.py populate_demo_producers --clear --count 50 --firebase
# docker compose exec web python manage.py populate_demo_producers --clear --count 75 --firebase
"""
Populate demo producer users.

Creates generated producer accounts with matching Producer profiles.

Generated account format:
- name: Producer 1, Producer 2, Producer 3...
- email: producer1@gmail.com, producer2@gmail.com, producer3@gmail.com...
- password: producerpass

By default, this command creates Django users only.

Use --firebase to also create or update matching Firebase Authentication
users. This is required when the login page uses Firebase authentication.
"""

import re

import firebase_admin
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from firebase_admin import auth as firebase_auth

from accounts.models import Address, Producer, User


FARM_NAMES = [
    "Avon Valley Farm",
    "Bristol Green Growers",
    "Redland Organic Farm",
    "Somerset Fresh Produce",
    "Cotswold Market Garden",
    "Harbourside Harvest",
    "Clifton Community Farm",
    "Southville Growers",
    "Easton Fresh Fields",
    "Mendip Meadow Farm",
    "Severn Valley Produce",
    "Bath Road Farm",
    "St Werburghs Growers",
    "West Country Roots",
    "Bristol Orchard Co",
    "Chew Valley Organics",
    "Gloucester Road Farm",
    "Knowle Fresh Produce",
    "Fishponds Farm Shop",
    "Bedminster Market Farm",
]


FARM_TYPES = [
    "seasonal vegetables",
    "fresh fruit",
    "leafy greens",
    "root vegetables",
    "organic produce",
    "local dairy alternatives",
    "artisan bakery produce",
    "herbs and salad crops",
    "orchard produce",
    "sustainable farm boxes",
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


PAYOUT_METHODS = [
    Producer.Payout_methods.BANK_TRANSFER,
    Producer.Payout_methods.PAY_PAL,
    Producer.Payout_methods.CHEQUE,
]


def build_uk_mobile(number, block):
    """
    Return a format-valid UK mobile number.

    Format:
    +44 7700 XXX XXX

    Example:
    +447700200001
    """
    return f"+447700{block + number:06d}"


def get_demo_address(offset):
    """
    Return a reusable Bristol-format demo address.
    """
    return UK_DEMO_ADDRESSES[offset % len(UK_DEMO_ADDRESSES)]


class Command(BaseCommand):
    help = "Create demo producer users and producer profiles."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=50,
            help="Number of demo producers to create. Default: 50.",
        )

        parser.add_argument(
            "--password",
            type=str,
            default="producerpass",
            help="Password assigned to generated demo producers.",
        )

        parser.add_argument(
            "--email-domain",
            type=str,
            default="gmail.com",
            help="Email domain for generated demo producers.",
        )

        parser.add_argument(
            "--start-index",
            type=int,
            default=1,
            help="Starting number for generated demo producers.",
        )

        parser.add_argument(
            "--reset-passwords",
            action="store_true",
            help="Reset passwords for existing matching Django demo producers.",
        )

        parser.add_argument(
            "--clear",
            action="store_true",
            help=(
                "Delete existing generated Django demo producers before creating "
                "new ones. Only users matching producer<number>@<email-domain> "
                "and name='Producer <number>' are deleted."
            ),
        )

        parser.add_argument(
            "--firebase",
            action="store_true",
            help=(
                "Also create or update matching Firebase Authentication users. "
                "Existing Firebase users are updated with the same password and "
                "display name."
            ),
        )

        parser.add_argument(
            "--unapproved",
            action="store_true",
            help=(
                "Create producers as unapproved. By default, demo producers are "
                "approved so they can be used immediately in demo flows."
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
        is_approved = not options["unapproved"]

        if count <= 0:
            raise CommandError("--count must be greater than 0.")

        if start_index <= 0:
            raise CommandError("--start-index must be greater than 0.")

        if use_firebase:
            self._ensure_firebase_initialised()

        if clear:
            deleted_total, deleted_breakdown = self._clear_demo_producers(
                email_domain=email_domain
            )

            self.stdout.write(
                self.style.WARNING(
                    f"Cleared existing Django demo producer data: "
                    f"{deleted_total} object(s) deleted."
                )
            )

            if deleted_breakdown:
                for model_name, deleted_count in deleted_breakdown.items():
                    self.stdout.write(f"- {model_name}: {deleted_count}")

        created_users = 0
        existing_users = 0
        created_profiles = 0
        updated_profiles = 0
        created_addresses = 0
        updated_addresses = 0
        firebase_created_users = 0
        firebase_updated_users = 0

        for offset in range(count):
            number = start_index + offset

            full_name = f"Producer {number}"
            email = f"producer{number}@{email_domain}"
            phone = build_uk_mobile(number=number, block=200000)
            address = get_demo_address(offset)

            user, user_created = User.objects.get_or_create(
                email=email,
                defaults={
                    "name": full_name,
                    "phone": phone,
                    "role": User.Role_choices.PRODUCER,
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

                if user.role != User.Role_choices.PRODUCER:
                    user.role = User.Role_choices.PRODUCER
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

            producer_defaults = self._build_producer_defaults(
                user=user,
                number=number,
                offset=offset,
                is_approved=is_approved,
                address=address,
            )

            producer, producer_created = Producer.objects.update_or_create(
                user=user,
                defaults=producer_defaults,
            )

            if producer_created:
                created_profiles += 1
            else:
                updated_profiles += 1

            _, address_created = Address.objects.update_or_create(
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

            if address_created:
                created_addresses += 1
            else:
                updated_addresses += 1

        self.stdout.write(self.style.SUCCESS("Demo producers populated successfully."))
        self.stdout.write(f"Created Django producer users: {created_users}")
        self.stdout.write(
            f"Existing Django producer users updated/skipped: {existing_users}"
        )
        self.stdout.write(f"Created producer profiles: {created_profiles}")
        self.stdout.write(f"Updated producer profiles: {updated_profiles}")
        self.stdout.write(f"Created producer addresses: {created_addresses}")
        self.stdout.write(f"Updated producer addresses: {updated_addresses}")

        if use_firebase:
            self.stdout.write(f"Created Firebase users: {firebase_created_users}")
            self.stdout.write(f"Updated Firebase users: {firebase_updated_users}")

        self.stdout.write(f"Approved producers: {'Yes' if is_approved else 'No'}")
        self.stdout.write(f"Default password for generated producers: {password}")

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

    def _clear_demo_producers(self, email_domain):
        """
        Delete only generated Django demo producers.

        This avoids deleting every producer account. The filter targets users
        created by this command, for example:

        producer1@gmail.com
        producer2@gmail.com
        producer50@gmail.com

        Extra safety:
        - role must be PRODUCER
        - name must start with 'Producer '
        - email must match producer<number>@<email-domain>

        Firebase users are not deleted here. When --firebase is used, existing
        Firebase users are updated instead.
        """
        escaped_domain = re.escape(email_domain)

        return User.objects.filter(
            email__regex=rf"^producer[0-9]+@{escaped_domain}$",
            name__startswith="Producer ",
            role=User.Role_choices.PRODUCER,
        ).delete()

    def _build_producer_defaults(
        self,
        user,
        number,
        offset,
        is_approved,
        address,
    ):
        farm_name_base = FARM_NAMES[offset % len(FARM_NAMES)]
        farm_type = FARM_TYPES[offset % len(FARM_TYPES)]
        payout_method = PAYOUT_METHODS[offset % len(PAYOUT_METHODS)]

        farm_name = f"{farm_name_base} {number}"
        contact_email = user.email
        contact_phone = user.phone

        approved_at = timezone.now() if is_approved else None

        defaults = {
            "approved_by_admin": None,
            "stripe_account_id": "",
            "farm_name": farm_name,
            "farm_description": (
                f"{farm_name} supplies {farm_type} for local households, "
                f"community groups and businesses across the Bristol region."
            ),
            "organic_certification_number": (
                f"ORG-{number:05d}" if offset % 3 == 0 else ""
            ),
            "farm_postcode": address["postcode"],
            "contact_email": contact_email,
            "contact_phone": contact_phone,
            "email_low_stock_notifications": offset % 2 == 0,
            "is_approved": is_approved,
            "approved_at": approved_at,
            "payout_method": payout_method,
            "bank_account_name": "",
            "bank_account_number": "",
            "bank_sort_code": "",
            "paypal_email": "",
            "payout_notes": "Generated demo producer account.",
            "cheque_payee_name": "",
            "cheque_postal_address": "",
        }

        if payout_method == Producer.Payout_methods.BANK_TRANSFER:
            defaults.update(
                {
                    "bank_account_name": farm_name,
                    "bank_account_number": f"{number:08d}"[-8:],
                    "bank_sort_code": "12-34-56",
                }
            )

        elif payout_method == Producer.Payout_methods.PAY_PAL:
            defaults.update(
                {
                    "paypal_email": f"producer{number}.paypal@demo.local",
                }
            )

        elif payout_method == Producer.Payout_methods.CHEQUE:
            defaults.update(
                {
                    "cheque_payee_name": farm_name,
                    "cheque_postal_address": (
                        f'{address["line1"]}, {address["city"]}, '
                        f'{address["postcode"]}'
                    ),
                }
            )

        return defaults