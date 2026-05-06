"""
Delete Firebase Authentication users from the configured Firebase project.

Default behaviour:
- Dry run only
- Prints matching users
- Deletes nothing

Use --confirm to actually delete users.

Examples:
docker compose exec web python manage.py clear_firebase_users
docker compose exec web python manage.py clear_firebase_users --confirm
docker compose exec web python manage.py clear_firebase_users --prefix user --domain gmail.com --confirm
"""

import firebase_admin
from django.core.management.base import BaseCommand, CommandError
from firebase_admin import auth as firebase_auth


class Command(BaseCommand):
    help = "Delete Firebase Authentication users from the configured Firebase project."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Actually delete matching Firebase users.",
        )

        parser.add_argument(
            "--prefix",
            type=str,
            default="user",
            help="Only target emails starting with this prefix. Default: user.",
        )

        parser.add_argument(
            "--domain",
            type=str,
            default="gmail.com",
            help="Only target emails using this domain. Default: gmail.com.",
        )

        parser.add_argument(
            "--all",
            action="store_true",
            help="Delete all Firebase Auth users in this Firebase project.",
        )

        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Firebase delete_users batch size. Maximum: 1000.",
        )

    def handle(self, *args, **options):
        confirm = options["confirm"]
        prefix = options["prefix"]
        domain = options["domain"]
        delete_all = options["all"]
        batch_size = options["batch_size"]

        if batch_size < 1 or batch_size > 1000:
            raise CommandError("--batch-size must be between 1 and 1000.")

        self._ensure_firebase_initialised()

        matched_uids = []
        matched_emails = []

        page = firebase_auth.list_users()

        while page:
            for user in page.users:
                email = user.email or ""

                if delete_all or self._email_matches(
                    email=email,
                    prefix=prefix,
                    domain=domain,
                ):
                    matched_uids.append(user.uid)
                    matched_emails.append(email)

            page = page.get_next_page()

        self.stdout.write(f"Matched Firebase users: {len(matched_uids)}")

        for email in matched_emails[:20]:
            self.stdout.write(f"- {email}")

        if len(matched_emails) > 20:
            self.stdout.write(f"...and {len(matched_emails) - 20} more")

        if not confirm:
            self.stdout.write(
                self.style.WARNING(
                    "Dry run only. Add --confirm to actually delete matched users."
                )
            )
            return

        if not matched_uids:
            self.stdout.write(self.style.SUCCESS("No Firebase users matched."))
            return

        deleted_count = 0
        failed_count = 0

        for index in range(0, len(matched_uids), batch_size):
            batch = matched_uids[index:index + batch_size]
            result = firebase_auth.delete_users(batch)

            deleted_count += result.success_count
            failed_count += result.failure_count

            if result.failure_count:
                for error in result.errors:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Failed index {error.index}: {error.reason}"
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Firebase deletion complete. Deleted: {deleted_count}. "
                f"Failed: {failed_count}."
            )
        )

    def _ensure_firebase_initialised(self):
        try:
            firebase_admin.get_app()
        except ValueError:
            try:
                firebase_admin.initialize_app()
            except Exception as exc:
                raise CommandError(
                    "Firebase could not be initialised. Check "
                    "GOOGLE_APPLICATION_CREDENTIALS inside Docker."
                ) from exc

    def _email_matches(self, email, prefix, domain):
        return (
            email.startswith(prefix)
            and email.endswith(f"@{domain}")
            and email[len(prefix):].split("@")[0].isdigit()
        )