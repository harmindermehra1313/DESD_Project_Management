# docker compose exec web python manage.py test products.tests.test_inventory_edge_cases -v 2

import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.test import TestCase
from django.urls import reverse

from accounts.models import Producer
from products.models import Category, Inventory, InventoryUpdateHistory, Product


class InventoryEdgeCaseTests(TestCase):
    """
    Automated tests for producer inventory update edge cases.

    Covers:
    - INV-EC-001 to INV-EC-016
    - batch creation validation
    - batch reduction validation
    - batch soft deletion
    - producer ownership protection
    - customer marketplace visibility
    """

    password = "StrongPass123!"

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    def _create_user(self, email, role="PRODUCER"):
        """
        Create a user while staying compatible with the custom user model.

        Some projects use email-only login, while others still require
        username/name/full_name fields.
        """
        User = get_user_model()

        user_kwargs = {
            "email": email,
            "password": self.password,
        }

        field_names = {field.name for field in User._meta.fields}

        if "username" in field_names:
            user_kwargs["username"] = email

        if "role" in field_names:
            user_kwargs["role"] = role

        if "name" in field_names:
            user_kwargs["name"] = email.split("@")[0]

        if "full_name" in field_names:
            user_kwargs["full_name"] = email.split("@")[0]

        return User.objects.create_user(**user_kwargs)

    def _create_model_with_existing_fields(self, model_class, **values):
        """
        Create a model object while ignoring fields that do not exist.

        This keeps the test setup tolerant of small model differences.
        """
        valid_field_names = {
            field.name
            for field in model_class._meta.fields
        }

        filtered_values = {
            key: value
            for key, value in values.items()
            if key in valid_field_names
        }

        return model_class.objects.create(**filtered_values)

    def _create_producer(self, user, farm_name):
        return self._create_model_with_existing_fields(
            Producer,
            user=user,
            farm_name=farm_name,
            business_name=farm_name,
            contact_name="Test Producer",
            full_name="Test Producer",
            phone="01179123456",
            contact_phone="01179123456",
            farm_postcode="BS1 5TR",
            postcode="BS1 5TR",
            payout_method="BANK",
        )

    def _create_category(self):
        return self._create_model_with_existing_fields(
            Category,
            name="Vegetables",
            description="",
            vat=Decimal("0.00"),
            food_groups="VEG",
        )

    def _create_product(self, producer, name="Organic Tomatoes"):
        return self._create_model_with_existing_fields(
            Product,
            producer=producer,
            category=self.category,
            name=name,
            price=Decimal("3.50"),
            availability_status=Product.Availability_status.AVAILABLE,
            status=Product.Status.PUBLISHED,
            unit="KG",
            organic_certification_status=Product.OrganicStatus.CERTIFIED,
            description="Fresh local produce.",
            farm_origin=producer.farm_name,
            low_stock_threshold=5,
        )

    def _create_batch(
        self,
        product,
        quantity=20,
        harvest_date=None,
        expiry_date=None,
        status="ACT",
    ):
        if harvest_date is None:
            harvest_date = date.today()

        if expiry_date is None:
            expiry_date = date.today() + timedelta(days=7)

        return self._create_model_with_existing_fields(
            Inventory,
            product=product,
            user=product.producer.user,
            original_quantity=quantity,
            remaining_quantity=quantity,
            harvest_date=harvest_date,
            expiry_date=expiry_date,
            expiry_type=Inventory.ExpiryType.BEST_BEFORE,
            status=status,
            surplus_status=Inventory.SurplusStatus.NONE,
            surplus_discount_percentage=0,
        )

    def setUp(self):
        self.category = self._create_category()

        self.producer_user = self._create_user(
            "producer1@example.com",
            role="PRODUCER",
        )
        self.other_producer_user = self._create_user(
            "producer2@example.com",
            role="PRODUCER",
        )

        self.producer = self._create_producer(
            self.producer_user,
            "Bristol Fresh Farm",
        )
        self.other_producer = self._create_producer(
            self.other_producer_user,
            "Somerset Test Farm",
        )

        self.product = self._create_product(
            self.producer,
            name="Organic Tomatoes",
        )
        self.batch = self._create_batch(
            self.product,
            quantity=20,
        )

        self.other_product = self._create_product(
            self.other_producer,
            name="Other Producer Carrots",
        )
        self.other_batch = self._create_batch(
            self.other_product,
            quantity=15,
        )

        self.client.force_login(self.producer_user)

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------

    def add_batch_url(self, product=None):
        product = product or self.product
        return reverse("products:add_batch", args=[product.pk])

    def reduce_batch_url(self, product=None):
        product = product or self.product
        return reverse("products:reduce_batch", args=[product.pk])

    def delete_batch_url(self, product=None):
        product = product or self.product
        return reverse("products:delete_batch", args=[product.pk])

    def edit_product_url(self, product=None):
        product = product or self.product
        return reverse("products:edit_producer_product", args=[product.pk])

    def marketplace_url(self):
        return reverse("products:product_view", args=[0])

    # ------------------------------------------------------------------
    # Request helpers
    # ------------------------------------------------------------------

    def post_json(self, url, payload):
        return self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def valid_add_batch_payload(self, **overrides):
        payload = {
            "original_quantity": 10,
            "harvest_date": date.today().isoformat(),
            "expiry_date": (date.today() + timedelta(days=7)).isoformat(),
            "expiry_type": Inventory.ExpiryType.BEST_BEFORE,
        }
        payload.update(overrides)
        return payload

    def valid_edit_payload(self, product=None, **overrides):
        product = product or self.product

        payload = {
            "name": product.name,
            "price": str(product.price),
            "unit": product.unit,
            "category_id": product.category_id,
            "availability_status": product.availability_status,
            "organic_certification_status": product.organic_certification_status,
            "description": product.description,
            "low_stock_threshold": product.low_stock_threshold,
            "wholesale_price": "",
            "wholesale_min_quantity": "",
        }
        payload.update(overrides)
        return payload

    def active_stock_total(self, product=None):
        product = product or self.product

        return (
            Inventory.objects.filter(product=product, status="ACT")
            .aggregate(total=Sum("remaining_quantity"))
            .get("total")
            or 0
        )

    # ------------------------------------------------------------------
    # INV-EC-001 to INV-EC-007: add batch validation
    # ------------------------------------------------------------------

    def test_inv_ec_001_rejects_zero_quantity_batch(self):
        before_count = Inventory.objects.filter(product=self.product).count()
        before_stock = self.active_stock_total()

        response = self.post_json(
            self.add_batch_url(),
            self.valid_add_batch_payload(original_quantity=0),
        )

        data = response.json()

        self.assertFalse(data["success"])
        self.assertIn("Quantity must be between 1 and 9999", data["error"])
        self.assertEqual(
            Inventory.objects.filter(product=self.product).count(),
            before_count,
        )
        self.assertEqual(self.active_stock_total(), before_stock)

    def test_inv_ec_002_rejects_quantity_above_allowed_maximum(self):
        before_count = Inventory.objects.filter(product=self.product).count()
        before_stock = self.active_stock_total()

        response = self.post_json(
            self.add_batch_url(),
            self.valid_add_batch_payload(original_quantity=10000),
        )

        data = response.json()

        self.assertFalse(data["success"])
        self.assertIn("Quantity must be between 1 and 9999", data["error"])
        self.assertEqual(
            Inventory.objects.filter(product=self.product).count(),
            before_count,
        )
        self.assertEqual(self.active_stock_total(), before_stock)

    def test_inv_ec_003_rejects_non_numeric_quantity(self):
        before_count = Inventory.objects.filter(product=self.product).count()
        before_stock = self.active_stock_total()

        response = self.post_json(
            self.add_batch_url(),
            self.valid_add_batch_payload(original_quantity="abc"),
        )

        data = response.json()

        self.assertFalse(data["success"])
        self.assertIn("Quantity must be between 1 and 9999", data["error"])
        self.assertEqual(
            Inventory.objects.filter(product=self.product).count(),
            before_count,
        )
        self.assertEqual(self.active_stock_total(), before_stock)

    def test_inv_ec_004_rejects_future_harvest_date(self):
        before_count = Inventory.objects.filter(product=self.product).count()

        response = self.post_json(
            self.add_batch_url(),
            self.valid_add_batch_payload(
                harvest_date=(date.today() + timedelta(days=1)).isoformat(),
            ),
        )

        data = response.json()

        self.assertFalse(data["success"])
        self.assertIn("Harvest date cannot be in the future", data["error"])
        self.assertEqual(
            Inventory.objects.filter(product=self.product).count(),
            before_count,
        )

    def test_inv_ec_005_rejects_harvest_date_more_than_30_days_old(self):
        before_count = Inventory.objects.filter(product=self.product).count()

        response = self.post_json(
            self.add_batch_url(),
            self.valid_add_batch_payload(
                harvest_date=(date.today() - timedelta(days=31)).isoformat(),
            ),
        )

        data = response.json()

        self.assertFalse(data["success"])
        self.assertIn(
            "Harvest date cannot be more than 30 days old",
            data["error"],
        )
        self.assertEqual(
            Inventory.objects.filter(product=self.product).count(),
            before_count,
        )

    def test_inv_ec_006_rejects_expiry_date_before_today(self):
        before_count = Inventory.objects.filter(product=self.product).count()

        response = self.post_json(
            self.add_batch_url(),
            self.valid_add_batch_payload(
                harvest_date=(date.today() - timedelta(days=2)).isoformat(),
                expiry_date=(date.today() - timedelta(days=1)).isoformat(),
            ),
        )

        data = response.json()

        self.assertFalse(data["success"])
        self.assertIn("Expiry date cannot be in the past", data["error"])
        self.assertEqual(
            Inventory.objects.filter(product=self.product).count(),
            before_count,
        )

    def test_inv_ec_007_rejects_expiry_date_before_harvest_date(self):
        """
        This invalid combination is rejected.

        Because the backend checks 'expiry date cannot be in the past' before
        'expiry date cannot be before harvest date', the returned message may
        be the past-date validation message for realistic dates.
        """
        before_count = Inventory.objects.filter(product=self.product).count()

        response = self.post_json(
            self.add_batch_url(),
            self.valid_add_batch_payload(
                harvest_date=date.today().isoformat(),
                expiry_date=(date.today() - timedelta(days=1)).isoformat(),
            ),
        )

        data = response.json()

        self.assertFalse(data["success"])
        self.assertIn("Expiry date", data["error"])
        self.assertEqual(
            Inventory.objects.filter(product=self.product).count(),
            before_count,
        )

    # ------------------------------------------------------------------
    # INV-EC-008 to INV-EC-010: reduce batch validation
    # ------------------------------------------------------------------

    def test_inv_ec_008_reduces_batch_by_exact_remaining_stock(self):
        response = self.post_json(
            self.reduce_batch_url(),
            {
                "batch_id": self.batch.pk,
                "amount": 20,
            },
        )

        data = response.json()
        self.batch.refresh_from_db()

        self.assertTrue(data["success"])
        self.assertEqual(self.batch.remaining_quantity, 0)
        self.assertEqual(data["total_stock"], 0)
        self.assertTrue(
            InventoryUpdateHistory.objects.filter(
                inventory=self.batch,
                field_changed="remaining_quantity",
                old_value="20",
                new_value="0",
            ).exists()
        )

    def test_inv_ec_009_rejects_reduction_above_remaining_stock(self):
        before_quantity = self.batch.remaining_quantity
        before_stock = self.active_stock_total()

        response = self.post_json(
            self.reduce_batch_url(),
            {
                "batch_id": self.batch.pk,
                "amount": 21,
            },
        )

        data = response.json()
        self.batch.refresh_from_db()

        self.assertFalse(data["success"])
        self.assertIn("Cannot reduce more than remaining stock", data["error"])
        self.assertEqual(self.batch.remaining_quantity, before_quantity)
        self.assertEqual(self.active_stock_total(), before_stock)

    def test_inv_ec_010_rejects_zero_negative_or_blank_reduction_amount(self):
        invalid_amounts = [0, -1, ""]

        for amount in invalid_amounts:
            with self.subTest(amount=amount):
                self.batch.remaining_quantity = 20
                self.batch.save(update_fields=["remaining_quantity"])

                response = self.post_json(
                    self.reduce_batch_url(),
                    {
                        "batch_id": self.batch.pk,
                        "amount": amount,
                    },
                )

                data = response.json()
                self.batch.refresh_from_db()

                self.assertFalse(data["success"])
                self.assertEqual(self.batch.remaining_quantity, 20)

    # ------------------------------------------------------------------
    # INV-EC-011 to INV-EC-012: delete batch and final stock
    # ------------------------------------------------------------------

    def test_inv_ec_011_soft_deletes_batch_and_records_history(self):
        response = self.post_json(
            self.delete_batch_url(),
            {
                "batch_id": self.batch.pk,
            },
        )

        data = response.json()
        self.batch.refresh_from_db()

        self.assertTrue(data["success"])
        self.assertEqual(self.batch.status, "DEL")
        self.assertEqual(data["total_stock"], 0)
        self.assertEqual(self.active_stock_total(), 0)
        self.assertTrue(
            InventoryUpdateHistory.objects.filter(
                inventory=self.batch,
                field_changed="batch_deleted",
                new_value="deleted",
            ).exists()
        )

    def test_inv_ec_012_deleting_final_active_batch_hides_product_from_marketplace(self):
        response = self.post_json(
            self.delete_batch_url(),
            {
                "batch_id": self.batch.pk,
            },
        )

        data = response.json()

        self.assertTrue(data["success"])
        self.assertEqual(data["total_stock"], 0)

        marketplace_response = self.client.get(self.marketplace_url())

        self.assertEqual(marketplace_response.status_code, 200)
        self.assertNotContains(marketplace_response, "Organic Tomatoes")

    # ------------------------------------------------------------------
    # INV-EC-013 to INV-EC-014: security and invalid JSON
    # ------------------------------------------------------------------

    def test_inv_ec_013_rejects_editing_another_producers_product(self):
        before_name = self.other_product.name
        before_price = self.other_product.price
        before_availability = self.other_product.availability_status

        response = self.post_json(
            self.edit_product_url(self.other_product),
            self.valid_edit_payload(
                self.other_product,
                name="Tampered Product Name",
                price="0.01",
                availability_status=Product.Availability_status.DISCONTINUED,
            ),
        )

        self.other_product.refresh_from_db()

        self.assertIn(response.status_code, [403, 404])
        self.assertEqual(self.other_product.name, before_name)
        self.assertEqual(self.other_product.price, before_price)
        self.assertEqual(
            self.other_product.availability_status,
            before_availability,
        )

    def test_inv_ec_014_rejects_invalid_json_for_add_batch_endpoint(self):
        before_count = Inventory.objects.filter(product=self.product).count()

        response = self.client.post(
            self.add_batch_url(),
            data="{invalid-json",
            content_type="application/json",
        )

        data = response.json()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(data["success"])
        self.assertIn("Invalid JSON", data["error"])
        self.assertEqual(
            Inventory.objects.filter(product=self.product).count(),
            before_count,
        )

    def test_inv_ec_014_rejects_invalid_json_for_edit_endpoint(self):
        before_name = self.product.name

        response = self.client.post(
            self.edit_product_url(),
            data="{invalid-json",
            content_type="application/json",
        )

        data = response.json()
        self.product.refresh_from_db()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(data["success"])
        self.assertIn("Invalid JSON", data["error"])
        self.assertEqual(self.product.name, before_name)

    # ------------------------------------------------------------------
    # INV-EC-015: expired active stock should not appear to customers
    # ------------------------------------------------------------------

    def test_inv_ec_015_hides_product_when_all_active_batches_are_expired(self):
        self.batch.expiry_date = date.today() - timedelta(days=1)
        self.batch.remaining_quantity = 20
        self.batch.status = "ACT"
        self.batch.save(
            update_fields=[
                "expiry_date",
                "remaining_quantity",
                "status",
            ]
        )

        marketplace_response = self.client.get(self.marketplace_url())

        self.assertEqual(marketplace_response.status_code, 200)
        self.assertNotContains(marketplace_response, "Organic Tomatoes")

    # ------------------------------------------------------------------
    # INV-EC-016: producer must not delete another producer's batch
    # ------------------------------------------------------------------

    def test_inv_ec_016_rejects_deleting_another_producers_batch(self):
        """
        Security test.

        Producer A is logged in.
        Producer A attempts to delete Producer B's batch by posting to
        Producer B's product delete-batch endpoint.

        Expected secure behaviour:
        - request is rejected, ideally 403 or 404
        - Producer B's batch remains active
        - no delete history is created for Producer B's batch

        This test may currently fail if delete_batch() does not filter the
        product by producer=request.user.producer_profile.
        """
        before_status = self.other_batch.status
        before_quantity = self.other_batch.remaining_quantity
        before_stock = self.active_stock_total(self.other_product)

        response = self.post_json(
            self.delete_batch_url(self.other_product),
            {
                "batch_id": self.other_batch.pk,
            },
        )

        self.other_batch.refresh_from_db()

        self.assertIn(response.status_code, [403, 404])
        self.assertEqual(self.other_batch.status, before_status)
        self.assertEqual(self.other_batch.remaining_quantity, before_quantity)
        self.assertEqual(
            self.active_stock_total(self.other_product),
            before_stock,
        )
        self.assertFalse(
            InventoryUpdateHistory.objects.filter(
                inventory=self.other_batch,
                field_changed="batch_deleted",
            ).exists()
        )