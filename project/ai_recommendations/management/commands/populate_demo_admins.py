# docker compose exec web python manage.py populate_demo_admins --clear --count 5
# docker compose exec web python manage.py populate_demo_admins --clear --count 5 --firebase

"""
Populate demo admin users.

Generated account format:
- name: Admin 1, Admin 2, Admin 3...
- email: admin1@gmail.com, admin2@gmail.com, admin3@gmail.com...
- password: adminpass

By default, this command creates Django admin users only.

Use --firebase to also create or update matching Firebase Authentication
users. This is required when the login page uses Firebase authentication.
"""

import re

import firebase_admin
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from firebase_admin import auth as firebase_auth

from accounts.models import Address, Admin, User


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
]


def build_uk_mobile(number, block):
    """
    Return a format-valid UK mobile number.

    Format:
    +44 7700 XXX XXX

    Example:
    +447700300001
    """
    return f"+447700{block + number:06d}"


def get_demo_address(offset):
    """
    Return a reusable Bristol-format demo address.
    """
    return UK_DEMO_ADDRESSES[offset % len(UK_DEMO_ADDRESSES)]


class Command(BaseCommand):
    help = "Create demo admin users and admin profiles."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=5,
            help="Number of demo admins to create. Default: 5.",
        )

        parser.add_argument(
            "--password",
            type=str,
            default="adminpass",
            help="Password assigned to generated demo admins.",
        )

        parser.add_argument(
            "--email-domain",
            type=str,
            default="gmail.com",
            help="Email domain for generated demo admins.",
        )

        parser.add_argument(
            "--start-index",
            type=int,
            default=1,
            help="Starting number for generated demo admins.",
        )

        parser.add_argument(
            "--reset-passwords",
            action="store_true",
            help="Reset passwords for existing matching Django demo admins.",
        )

        parser.add_argument(
            "--clear",
            action="store_true",
            help=(
                "Delete existing generated Django demo admins before creating "
                "new ones. Only users matching admin<number>@<email-domain> "
                "and name='Admin <number>' are deleted."
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
            deleted_total, deleted_breakdown = self._clear_demo_admins(
                email_domain=email_domain
            )

            self.stdout.write(
                self.style.WARNING(
                    f"Cleared existing Django demo admin data: "
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

            full_name = f"Admin {number}"
            email = f"admin{number}@{email_domain}"
            phone = build_uk_mobile(number=number, block=300000)
            address = get_demo_address(offset)

            user, user_created = User.objects.get_or_create(
                email=email,
                defaults={
                    "name": full_name,
                    "phone": phone,
                    "role": User.Role_choices.ADMIN,
                    "is_active": True,
                    "is_staff": True,
                    "is_superuser": True,
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

                if user.role != User.Role_choices.ADMIN:
                    user.role = User.Role_choices.ADMIN
                    changed_fields.append("role")

                if not user.is_active:
                    user.is_active = True
                    changed_fields.append("is_active")

                if not user.is_staff:
                    user.is_staff = True
                    changed_fields.append("is_staff")

                if not user.is_superuser:
                    user.is_superuser = True
                    changed_fields.append("is_superuser")

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

            admin_defaults = {
                "permissions_json": {
                    "demo_admin": True,
                    "can_manage_users": True,
                    "can_manage_products": True,
                    "can_manage_orders": True,
                    "can_manage_reviews": True,
                    "can_view_dashboard": True,
                }
            }

            admin_profile, admin_created = Admin.objects.update_or_create(
                user=user,
                defaults=admin_defaults,
            )

            if admin_created:
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

        self.stdout.write(self.style.SUCCESS("Demo admins populated successfully."))
        self.stdout.write(f"Created Django admin users: {created_users}")
        self.stdout.write(f"Existing Django admin users updated/skipped: {existing_users}")
        self.stdout.write(f"Created admin profiles: {created_profiles}")
        self.stdout.write(f"Updated admin profiles: {updated_profiles}")
        self.stdout.write(f"Created admin addresses: {created_addresses}")
        self.stdout.write(f"Updated admin addresses: {updated_addresses}")

        if use_firebase:
            self.stdout.write(f"Created Firebase users: {firebase_created_users}")
            self.stdout.write(f"Updated Firebase users: {firebase_updated_users}")

        self.stdout.write(f"Default password for generated admins: {password}")

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

    def _clear_demo_admins(self, email_domain):
        """
        Delete only generated Django demo admins.

        This avoids deleting every admin account. The filter targets users
        created by this command, for example:

        admin1@gmail.com
        admin2@gmail.com
        admin5@gmail.com

        Extra safety:
        - role must be ADMIN
        - name must start with 'Admin '
        - email must match admin<number>@<email-domain>

        Firebase users are not deleted here. When --firebase is used, existing
        Firebase users are updated instead.
        """
        escaped_domain = re.escape(email_domain)

        return User.objects.filter(
            email__regex=rf"^admin[0-9]+@{escaped_domain}$",
            name__startswith="Admin ",
            role=User.Role_choices.ADMIN,
        ).delete()