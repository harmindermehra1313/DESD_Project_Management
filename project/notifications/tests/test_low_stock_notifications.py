# docker compose exec web python manage.py test notifications.tests.test_low_stock_notifications -v 2

import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import timezone

from accounts.models import Producer
from notifications.models import Notification
from products.models import Category, Inventory, Product

from products.views.batch import (
    add_batch,
    delete_batch,
    reduce_batch,
    trigger_low_stock_notification,
)
from products.views.views_main import edit_producer_product


class LowStockNotificationEdgeCaseTests(TestCase):
    """
    Automated edge tests for TC-023:
    Low-stock notification generation, duplicate prevention, resolution,
    invalid stock reduction, batch add/delete, and threshold validation.
    """

    def setUp(self):
        self.factory = RequestFactory()

        self.user = self._create_user()
        self.producer = self._create_producer(self.user)
        self.category = self._create_category()

        self.product = Product.objects.create(
            producer=self.producer,
            category=self.category,
            name="Fresh Eggs",
            price=Decimal("3.50"),
            unit=self._first_choice_value(Product.Unit),
            availability_status=Product.Availability_status.AVAILABLE,
            organic_certification_status=Product.OrganicStatus.NOT_CERTIFIED,
            description="Local fresh eggs.",
            farm_origin=self.producer.farm_name,
            status=Product.Status.PUBLISHED,
            low_stock_threshold=10,
        )

        self.batch = self._create_batch(quantity=50)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_user(self):
        """
        Creates a test producer user.

        The email/password match the requested demo account:
        producer1@gmail.com / producerpass

        TestCase uses a separate temporary test database, so this account is
        created for the test run instead of being read from the development DB.
        """
        User = get_user_model()

        user_kwargs = {
            "email": "producer1@gmail.com",
            "password": "producerpass",
        }

        if any(field.name == "username" for field in User._meta.fields):
            user_kwargs["username"] = "producer1"

        user = User.objects.create_user(**user_kwargs)

        if hasattr(user, "role"):
            user.role = self._get_producer_role_value(User)
            user.save(update_fields=["role"])

        return user

    def _get_producer_role_value(self, User):
        """
        Finds the stored database value for the producer role.

        This avoids PermissionDenied when the project stores producer as
        PRODUCER, producer, PRO, or another role choice value.
        """
        try:
            role_field = User._meta.get_field("role")
        except Exception:
            return "PRODUCER"

        choices = getattr(role_field, "choices", None) or []

        for value, label in choices:
            value_text = str(value).lower()
            label_text = str(label).lower()

            if "producer" in value_text or "producer" in label_text:
                return value

        return "PRODUCER"

    def _create_producer(self, user):
        """
        Creates a producer profile linked to the test user.
        """
        producer, _ = Producer.objects.get_or_create(
            user=user,
            defaults={
                "farm_name": "TC023 Test Farm",
            },
        )

        return producer

    def _create_category(self):
        """
        Creates a product category with all required database fields.
        """
        return Category.objects.create(
            name="Dairy and Eggs",
            description="Test dairy and eggs category.",
            vat=Decimal("0.00"),
            food_groups="DAE",
        )

    def _first_choice_value(self, choices_class):
        return choices_class.choices[0][0]

    def _create_batch(self, quantity, product=None):
        product = product or self.product

        return Inventory.objects.create(
            product=product,
            user=self.user,
            original_quantity=quantity,
            remaining_quantity=quantity,
            harvest_date=date.today(),
            expiry_date=date.today() + timedelta(days=7),
            expiry_type=Inventory.ExpiryType.BEST_BEFORE,
            surplus_status=Inventory.SurplusStatus.NONE,
            surplus_discount_percentage=0,
            status=Inventory.BatchStatus.ACTIVE,
        )

    def _set_stock(self, quantity):
        self.batch.remaining_quantity = quantity
        self.batch.original_quantity = max(self.batch.original_quantity, quantity)
        self.batch.status = Inventory.BatchStatus.ACTIVE
        self.batch.save()

    def _active_alerts(self):
        return Notification.objects.filter(
            user=self.user,
            product=self.product,
            type=Notification.Type.PRODUCT_ALERT,
            resolved_at__isnull=True,
        )

    def _all_alerts(self):
        return Notification.objects.filter(
            user=self.user,
            product=self.product,
            type=Notification.Type.PRODUCT_ALERT,
        )

    def _post_json_to_view(self, view_func, product, payload):
        request = self.factory.post(
            "/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        request.user = self.user

        return view_func(request, product.pk)

    def _edit_payload(self, threshold):
        return {
            "name": self.product.name,
            "price": str(self.product.price),
            "unit": self.product.unit,
            "availability_status": self.product.availability_status,
            "organic_certification_status": self.product.organic_certification_status,
            "category_id": self.category.id,
            "description": self.product.description,
            "wholesale_price": "",
            "wholesale_min_quantity": "",
            "low_stock_threshold": threshold,
        }

    # ------------------------------------------------------------------
    # TC023-EC-001
    # ------------------------------------------------------------------

    def test_ec001_stock_equal_to_threshold_creates_alert(self):
        """
        Stock is exactly equal to threshold.

        Expected:
        Low-stock alert is generated because logic uses stock <= threshold.
        """
        self._set_stock(10)

        trigger_low_stock_notification(self.product)

        self.assertEqual(self._active_alerts().count(), 1)
        self.assertIn("Fresh Eggs", self._active_alerts().first().message)
        self.assertIn("10", self._active_alerts().first().message)

    # ------------------------------------------------------------------
    # TC023-EC-002
    # ------------------------------------------------------------------

    def test_ec002_stock_above_threshold_does_not_create_alert_and_resolves_existing(self):
        """
        Stock is just above threshold.

        Expected:
        No active alert remains. Existing unresolved alert is resolved.
        """
        self._set_stock(9)
        trigger_low_stock_notification(self.product)

        existing_alert = self._active_alerts().first()
        self.assertIsNotNone(existing_alert)

        self._set_stock(11)
        trigger_low_stock_notification(self.product)

        existing_alert.refresh_from_db()
        self.assertIsNotNone(existing_alert.resolved_at)
        self.assertEqual(self._active_alerts().count(), 0)

    # ------------------------------------------------------------------
    # TC023-EC-003
    # ------------------------------------------------------------------

    def test_ec003_stock_drops_from_11_to_10_creates_alert(self):
        """
        Stock drops from 11 to 10.

        Expected:
        Alert is generated because stock reached the threshold.
        """
        self._set_stock(11)
        trigger_low_stock_notification(self.product)
        self.assertEqual(self._active_alerts().count(), 0)

        self._set_stock(10)
        trigger_low_stock_notification(self.product)

        self.assertEqual(self._active_alerts().count(), 1)

    # ------------------------------------------------------------------
    # TC023-EC-004
    # ------------------------------------------------------------------

    def test_ec004_stock_drops_from_11_to_9_creates_alert_with_updated_stock(self):
        """
        Stock drops from 11 to 9.

        Expected:
        Alert is generated with the updated stock level.
        """
        self._set_stock(11)
        trigger_low_stock_notification(self.product)
        self.assertEqual(self._active_alerts().count(), 0)

        self._set_stock(9)
        trigger_low_stock_notification(self.product)

        alert = self._active_alerts().first()
        self.assertIsNotNone(alert)
        self.assertIn("Fresh Eggs", alert.message)
        self.assertIn("9", alert.message)

    # ------------------------------------------------------------------
    # TC023-EC-005
    # ------------------------------------------------------------------

    def test_ec005_duplicate_unresolved_alert_is_not_created(self):
        """
        Stock is already below threshold and unresolved alert already exists.

        Expected:
        No duplicate notification is created.
        """
        self._set_stock(9)
        trigger_low_stock_notification(self.product)
        trigger_low_stock_notification(self.product)

        self.assertEqual(self._active_alerts().count(), 1)
        self.assertEqual(self._all_alerts().count(), 1)

    # ------------------------------------------------------------------
    # TC023-EC-006
    # ------------------------------------------------------------------

    def test_ec006_read_alert_is_not_same_as_resolved_alert(self):
        """
        Existing alert is marked as read, then stock is reduced again while
        still below threshold.

        Expected:
        No new alert is created because read_at does not equal resolved_at.
        """
        self._set_stock(9)
        trigger_low_stock_notification(self.product)

        alert = self._active_alerts().first()
        alert.read_at = timezone.now()
        alert.save(update_fields=["read_at"])

        self._set_stock(8)
        trigger_low_stock_notification(self.product)

        alert.refresh_from_db()

        self.assertEqual(self._active_alerts().count(), 1)
        self.assertEqual(self._all_alerts().count(), 1)
        self.assertIsNotNone(alert.read_at)
        self.assertIsNone(alert.resolved_at)

    # ------------------------------------------------------------------
    # TC023-EC-007
    # ------------------------------------------------------------------

    def test_ec007_replenish_stock_from_9_to_40_resolves_alert(self):
        """
        Stock is replenished from 9 to 40 when threshold is 10.

        Expected:
        Existing low-stock alert is resolved.
        """
        self._set_stock(9)
        trigger_low_stock_notification(self.product)

        alert = self._active_alerts().first()
        self.assertIsNotNone(alert)

        self._set_stock(40)
        trigger_low_stock_notification(self.product)

        alert.refresh_from_db()
        self.assertIsNotNone(alert.resolved_at)
        self.assertEqual(self._active_alerts().count(), 0)

    # ------------------------------------------------------------------
    # TC023-EC-008
    # ------------------------------------------------------------------

    def test_ec008_replenish_stock_to_exact_threshold_keeps_alert_active(self):
        """
        Stock is replenished from 9 to exactly 10 when threshold is 10.

        Expected:
        Alert remains active because stock is still <= threshold.
        """
        self._set_stock(9)
        trigger_low_stock_notification(self.product)

        self._set_stock(10)
        trigger_low_stock_notification(self.product)

        alert = self._active_alerts().first()
        self.assertIsNotNone(alert)
        self.assertIsNone(alert.resolved_at)
        self.assertEqual(self._active_alerts().count(), 1)

    # ------------------------------------------------------------------
    # TC023-EC-009
    # ------------------------------------------------------------------

    def test_ec009_reduce_stock_by_zero_is_rejected(self):
        """
        Producer tries to reduce stock by 0.

        Expected:
        Request is rejected with validation message.
        """
        self._set_stock(20)

        response = self._post_json_to_view(
            reduce_batch,
            self.product,
            {
                "batch_id": self.batch.id,
                "amount": 0,
            },
        )

        data = json.loads(response.content.decode("utf-8"))

        self.batch.refresh_from_db()

        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "Reduction amount must be at least 1.")
        self.assertEqual(self.batch.remaining_quantity, 20)

    # ------------------------------------------------------------------
    # TC023-EC-010
    # ------------------------------------------------------------------

    def test_ec010_reduce_more_than_remaining_stock_is_rejected(self):
        """
        Producer tries to reduce stock by more than the remaining batch quantity.

        Expected:
        Request is rejected, stock is unchanged, and no incorrect alert is created.
        """
        self._set_stock(5)

        response = self._post_json_to_view(
            reduce_batch,
            self.product,
            {
                "batch_id": self.batch.id,
                "amount": 6,
            },
        )

        data = json.loads(response.content.decode("utf-8"))

        self.batch.refresh_from_db()

        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "Cannot reduce more than remaining stock.")
        self.assertEqual(self.batch.remaining_quantity, 5)
        self.assertEqual(self._active_alerts().count(), 0)

    # ------------------------------------------------------------------
    # TC023-EC-011
    # ------------------------------------------------------------------

    def test_ec011_batch_deletion_causes_low_stock_alert(self):
        """
        Producer deletes an active batch, causing total active stock to fall
        below threshold.

        Expected:
        Low-stock alert is generated after total stock is recalculated.
        """
        self._set_stock(8)
        second_batch = self._create_batch(quantity=5)

        # Total stock = 13, threshold = 10
        trigger_low_stock_notification(self.product)
        self.assertEqual(self._active_alerts().count(), 0)

        response = self._post_json_to_view(
            delete_batch,
            self.product,
            {
                "batch_id": second_batch.id,
            },
        )

        data = json.loads(response.content.decode("utf-8"))

        self.assertTrue(data["success"])
        self.assertEqual(data["total_stock"], 8)
        self.assertEqual(self._active_alerts().count(), 1)

    # ------------------------------------------------------------------
    # TC023-EC-012
    # ------------------------------------------------------------------

    def test_ec012_batch_addition_keeps_stock_below_threshold_without_duplicate(self):
        """
        Producer adds a new batch, but total stock is still below threshold.

        Expected:
        Existing unresolved alert remains active; duplicate alert is not created.
        """
        self._set_stock(3)
        trigger_low_stock_notification(self.product)

        self.assertEqual(self._active_alerts().count(), 1)

        response = self._post_json_to_view(
            add_batch,
            self.product,
            {
                "original_quantity": 4,
                "harvest_date": date.today().isoformat(),
                "expiry_date": (date.today() + timedelta(days=7)).isoformat(),
                "expiry_type": Inventory.ExpiryType.BEST_BEFORE,
            },
        )

        data = json.loads(response.content.decode("utf-8"))

        self.assertTrue(data["success"])
        self.assertEqual(data["total_stock"], 7)
        self.assertEqual(self._active_alerts().count(), 1)
        self.assertEqual(self._all_alerts().count(), 1)

    # ------------------------------------------------------------------
    # TC023-EC-013
    # ------------------------------------------------------------------

    def test_ec013_batch_addition_above_threshold_resolves_alert(self):
        """
        Producer adds a new batch and total stock rises above threshold.

        Expected:
        Existing low-stock alert is resolved.
        """
        self._set_stock(3)
        trigger_low_stock_notification(self.product)

        alert = self._active_alerts().first()
        self.assertIsNotNone(alert)

        response = self._post_json_to_view(
            add_batch,
            self.product,
            {
                "original_quantity": 20,
                "harvest_date": date.today().isoformat(),
                "expiry_date": (date.today() + timedelta(days=7)).isoformat(),
                "expiry_type": Inventory.ExpiryType.BEST_BEFORE,
            },
        )

        data = json.loads(response.content.decode("utf-8"))

        alert.refresh_from_db()

        self.assertTrue(data["success"])
        self.assertEqual(data["total_stock"], 23)
        self.assertIsNotNone(alert.resolved_at)
        self.assertEqual(self._active_alerts().count(), 0)

    # ------------------------------------------------------------------
    # TC023-EC-014
    # ------------------------------------------------------------------

    def test_ec014_threshold_increase_creates_alert_when_stock_is_below_new_threshold(self):
        """
        Producer increases threshold from 10 to 50 while stock is 40.

        Expected:
        Low-stock alert is generated because stock is below the new threshold.
        """
        self._set_stock(40)

        self.product.low_stock_threshold = 10
        self.product.save(update_fields=["low_stock_threshold"])

        trigger_low_stock_notification(self.product)
        self.assertEqual(self._active_alerts().count(), 0)

        response = self._post_json_to_view(
            edit_producer_product,
            self.product,
            self._edit_payload(threshold=50),
        )

        data = json.loads(response.content.decode("utf-8"))

        self.product.refresh_from_db()

        self.assertTrue(data["success"])
        self.assertEqual(self.product.low_stock_threshold, 50)
        self.assertEqual(self._active_alerts().count(), 1)

    # ------------------------------------------------------------------
    # TC023-EC-015
    # ------------------------------------------------------------------

    def test_ec015_invalid_threshold_values_are_rejected(self):
        """
        Producer enters invalid threshold values.

        Expected:
        Threshold update is rejected with validation message.
        """
        invalid_values = [-1, "abc", 10000]

        for invalid_value in invalid_values:
            with self.subTest(invalid_value=invalid_value):
                self.product.low_stock_threshold = 10
                self.product.save(update_fields=["low_stock_threshold"])

                response = self._post_json_to_view(
                    edit_producer_product,
                    self.product,
                    self._edit_payload(threshold=invalid_value),
                )

                data = json.loads(response.content.decode("utf-8"))

                self.product.refresh_from_db()

                self.assertFalse(data["success"])
                self.assertEqual(
                    data["error"],
                    "Low stock threshold must be a number between 0 and 9999.",
                )
                self.assertEqual(self.product.low_stock_threshold, 10)