from copy import deepcopy
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import NoReverseMatch, reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Producer


REGISTER_URL = "/accounts/api/register/"
PRODUCER_DASHBOARD_URL = "/producer/"


def optional_reverse(name, fallback, kwargs=None):
    """
    Use named URLs when available, otherwise fall back to a path.

    This keeps the tests usable even if URL names differ between branches.
    """
    try:
        return reverse(name, kwargs=kwargs)
    except NoReverseMatch:
        return fallback


class ProducerRegistrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.User = get_user_model()

        self.firebase_patcher = patch(
            "accounts.serializers.registration_producer.firebase_auth.create_user"
        )
        self.mock_firebase_create_user = self.firebase_patcher.start()
        self.addCleanup(self.firebase_patcher.stop)

    def valid_payload(self, email="jane.smith@bristolvalleyfarm.com"):
        return {
            "role": "producer",
            "name": "Jane Smith",
            "email": email,
            "phone": "+441179123456",
            "password": "ProducerTest@12345",
            "confirm_password": "ProducerTest@12345",
            "accept_terms": True,
            "farm_name": "Bristol Valley Farm",
            "farm_description": "Local Bristol producer.",
            "organic_certification_number": "AB-12345",
            "farm_postcode": "BS1 4DJ",
            "contact_email": "jane@gmail.com",
            "contact_phone": "+441179123456",
            "payout_method": "BANK_TRANSFER",
            "bank_account_name": "Bristol Valley Farm",
            "bank_account_number": "12345678",
            "bank_sort_code": "12-34-56",
        }

    def post_registration(self, payload):
        return self.client.post(REGISTER_URL, payload, format="json")

    def assert_no_account_created(self, email):
        self.assertFalse(
            self.User.objects.filter(email__iexact=email).exists(),
            "No User row should be created for invalid registration data.",
        )
        self.assertFalse(
            Producer.objects.filter(user__email__iexact=email).exists(),
            "No Producer row should be created for invalid registration data.",
        )

    def assert_registration_rejected(self, payload, expected_field=None):
        email = payload.get("email", "missing@example.com")

        response = self.post_registration(payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        if expected_field:
            self.assertIn(
                expected_field,
                response.data,
                f"Expected validation error for field: {expected_field}",
            )

        self.assert_no_account_created(email)

        return response

    # REG-001
    def test_valid_producer_registration_creates_user_and_profile(self):
        payload = self.valid_payload()

        response = self.post_registration(payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("registered successfully", response.data["message"].lower())

        user = self.User.objects.get(email=payload["email"])
        self.assertEqual(user.role, "PRODUCER")
        self.assertTrue(user.check_password(payload["password"]))

        producer = Producer.objects.get(user=user)
        self.assertEqual(producer.farm_name, "Bristol Valley Farm")
        self.assertEqual(producer.farm_postcode, "BS1 4DJ")
        self.assertEqual(producer.contact_email, "jane@gmail.com")
        self.assertEqual(producer.contact_phone, "+441179123456")

    # REG-002
    def test_missing_business_farm_name_is_rejected(self):
        payload = self.valid_payload(email="missing.farm@example.com")
        payload.pop("farm_name")

        self.assert_registration_rejected(payload, expected_field="farm_name")

    # REG-003
    def test_missing_contact_name_full_name_is_rejected(self):
        payload = self.valid_payload(email="missing.name@example.com")
        payload.pop("name")

        self.assert_registration_rejected(payload, expected_field="name")

    # REG-004
    def test_invalid_email_format_is_rejected(self):
        payload = self.valid_payload(email="jane@")

        response = self.post_registration(payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    # REG-005
    def test_duplicate_email_address_is_rejected(self):
        email = "duplicate.producer@example.com"

        first_response = self.post_registration(self.valid_payload(email=email))
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)

        second_response = self.post_registration(self.valid_payload(email=email))

        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.User.objects.filter(email__iexact=email).count(), 1)
        self.assertEqual(Producer.objects.filter(user__email__iexact=email).count(), 1)

    # REG-006
    def test_password_and_confirm_password_mismatch_is_rejected(self):
        payload = self.valid_payload(email="password.mismatch@example.com")
        payload["confirm_password"] = "DifferentPassword@12345"

        response = self.assert_registration_rejected(payload)

        self.assertIn("password", response.data)

    # REG-007
    def test_weak_password_is_rejected(self):
        payload = self.valid_payload(email="weak.password@example.com")
        payload["password"] = "password123"
        payload["confirm_password"] = "password123"

        self.assert_registration_rejected(payload)

    # REG-008
    def test_terms_not_accepted_is_rejected(self):
        payload = self.valid_payload(email="terms.not.accepted@example.com")
        payload["accept_terms"] = False

        response = self.assert_registration_rejected(payload)

        self.assertIn("accept_terms", response.data)

    # REG-009
    def test_missing_or_invalid_payout_method_is_rejected(self):
        missing_payload = self.valid_payload(email="missing.payout@example.com")
        missing_payload.pop("payout_method")

        invalid_payload = self.valid_payload(email="invalid.payout@example.com")
        invalid_payload["payout_method"] = "CRYPTO"

        with self.subTest("missing payout method"):
            self.assert_registration_rejected(
                missing_payload,
                expected_field="payout_method",
            )

        with self.subTest("invalid payout method"):
            self.assert_registration_rejected(
                invalid_payload,
                expected_field="payout_method",
            )

    # REG-010
    def test_invalid_uk_phone_number_is_rejected(self):
        payload = self.valid_payload(email="invalid.phone@example.com")
        payload["phone"] = "abc123"
        payload["contact_phone"] = "abc123"

        response = self.assert_registration_rejected(payload)

        self.assertTrue(
            "phone" in response.data or "contact_phone" in response.data,
            "Expected a validation error for phone/contact_phone.",
        )

    # REG-011
    def test_invalid_uk_postcode_is_rejected(self):
        payload = self.valid_payload(email="invalid.postcode@example.com")
        payload["farm_postcode"] = "ABCDE"

        self.assert_registration_rejected(payload, expected_field="farm_postcode")

    # REG-012
    def test_valid_local_uk_phone_format_is_accepted_or_normalised(self):
        payload = self.valid_payload(email="local.phone@example.com")
        payload["phone"] = "01179 123456"
        payload["contact_phone"] = "01179 123456"

        response = self.post_registration(payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = self.User.objects.get(email=payload["email"])
        producer = Producer.objects.get(user=user)

        self.assertIn(user.phone, {"01179 123456", "+441179123456"})
        self.assertIn(producer.contact_phone, {"01179 123456", "+441179123456"})

    # REG-013
    def test_failed_registration_creates_no_partial_user_or_producer(self):
        payload = self.valid_payload(email="partial.failure@example.com")
        payload["confirm_password"] = "WrongPassword@12345"

        user_count_before = self.User.objects.count()
        producer_count_before = Producer.objects.count()

        response = self.post_registration(payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.User.objects.count(), user_count_before)
        self.assertEqual(Producer.objects.count(), producer_count_before)
        self.assert_no_account_created(payload["email"])

    # REG-014
    def test_successful_registration_stores_password_as_hash(self):
        payload = self.valid_payload(email="hashed.password@example.com")

        response = self.post_registration(payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = self.User.objects.get(email=payload["email"])

        self.assertNotEqual(user.password, payload["password"])
        self.assertTrue(user.check_password(payload["password"]))
        self.assertIn("$", user.password)

    # SEC-001
    def test_security_role_admin_payload_does_not_create_admin_account(self):
        payload = self.valid_payload(email="malicious.admin@example.com")
        payload["role"] = "ADMIN"

        response = self.post_registration(payload)

        self.assertNotEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(
            self.User.objects.filter(email=payload["email"], role="ADMIN").exists()
        )

    # SEC-002
    def test_security_missing_or_changed_role_does_not_create_privileged_account(self):
        missing_role_payload = self.valid_payload(email="missing.role@example.com")
        missing_role_payload.pop("role")

        changed_role_payload = self.valid_payload(email="changed.role@example.com")
        changed_role_payload["role"] = "customer"

        for payload in [missing_role_payload, changed_role_payload]:
            with self.subTest(email=payload["email"]):
                response = self.post_registration(payload)

                self.assertNotEqual(response.status_code, status.HTTP_201_CREATED)
                self.assertFalse(
                    self.User.objects.filter(
                        email=payload["email"],
                        role__in=["PRODUCER", "ADMIN"],
                    ).exists()
                )

    # SEC-003
    def test_security_unauthenticated_user_cannot_access_producer_dashboard(self):
        url = optional_reverse("home:producer", PRODUCER_DASHBOARD_URL)

        response = self.client.get(url)

        self.assertIn(
            response.status_code,
            [status.HTTP_302_FOUND, status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    # SEC-004
    def test_security_customer_cannot_access_producer_dashboard(self):
        customer = self.User.objects.create_user(
            email="customer@example.com",
            password="CustomerTest@12345",
            name="Customer User",
            phone="+447123456789",
            role="CUSTOMER",
        )

        self.client.force_login(customer)

        url = optional_reverse("home:producer", PRODUCER_DASHBOARD_URL)
        response = self.client.get(url)

        self.assertIn(
            response.status_code,
            [status.HTTP_302_FOUND, status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    # SEC-005
    def test_security_producer_cannot_update_non_owned_or_invalid_order_status(self):
        """
        Security smoke test for producer order-status ownership.

        If a real ProducerOrderSummary fixture/factory already exists, replace
        `unauthorised_summary_id = 999999` with the ID of another producer's
        summary. Expected result must still be non-success.
        """
        producer_user = self.User.objects.create_user(
            email="producer.security@example.com",
            password="ProducerTest@12345",
            name="Security Producer",
            phone="+441179123456",
            role="PRODUCER",
        )

        Producer.objects.create(
            user=producer_user,
            farm_name="Security Farm",
            farm_postcode="BS1 4DJ",
            contact_email="producer.security@example.com",
            contact_phone="+441179123456",
            payout_method="BANK_TRANSFER",
        )

        self.client.force_login(producer_user)

        unauthorised_summary_id = 999999
        url = optional_reverse(
            "home:update_order_status",
            f"/producer/orders/{unauthorised_summary_id}/status/",
            kwargs={"summary_id": unauthorised_summary_id},
        )

        response = self.client.post(
            url,
            {"status": "SHP"},
            format="json",
        )

        self.assertIn(
            response.status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND],
        )