# docker compose exec web python manage.py test orders.tests.test_reorder_service --keepdb
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import ANY, call, patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from orders.models import Order
from orders.services.reorder_service import (
    _inventory_reorderable,
    _product_reorderable,
    reorder_order,
)


class FakeItemsManager:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)


class FakeProducer:
    def __init__(self, pk, name):
        self.pk = pk
        self.name = name

    def __str__(self):
        return self.name


class FakeProduct:
    class Status:
        PUBLISHED = "PUB"
        HIDDEN = "HID"
        FLAGGED = "FLG"
        REMOVED = "RMV"

    class Availability_status:
        AVAILABLE = "AV"
        OUT_OF_STOCK = "OOS"
        DISCONTINUED = "DIS"

    def __init__(
        self,
        pk,
        name,
        price=Decimal("10.00"),
        status="PUB",
        availability_status="AV",
    ):
        self.pk = pk
        self.name = name
        self.price = price
        self.status = status
        self.availability_status = availability_status


class FakeInventory:
    class ExpiryType:
        BEST_BEFORE = "BB"
        USE_BY = "UB"

    def __init__(
        self,
        pk,
        remaining_quantity,
        expiry_date,
        expiry_type="BB",
    ):
        self.pk = pk
        self.remaining_quantity = remaining_quantity
        self.expiry_date = expiry_date
        self.expiry_type = expiry_type


class FakeOrderItem:
    def __init__(
        self,
        *,
        product,
        inventory,
        producer,
        quantity,
        original_unit_price,
        producer_id=None,
    ):
        self.product = product
        self.inventory = inventory
        self.producer = producer
        self.quantity = quantity
        self.original_unit_price = original_unit_price
        self.producer_id = producer_id if producer_id is not None else producer.pk


class FakeOrder:
    def __init__(self, items):
        self.items = FakeItemsManager(items)


class ProductReorderableTests(TestCase):
    def test_product_reorderable_when_published_and_available(self):
        product = FakeProduct(
            pk=1,
            name="Apples",
            status=FakeProduct.Status.PUBLISHED,
            availability_status=FakeProduct.Availability_status.AVAILABLE,
        )

        ok, reason = _product_reorderable(product)

        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_product_not_reorderable_when_not_published(self):
        product = FakeProduct(
            pk=1,
            name="Apples",
            status=FakeProduct.Status.HIDDEN,
            availability_status=FakeProduct.Availability_status.AVAILABLE,
        )

        ok, reason = _product_reorderable(product)

        self.assertFalse(ok)
        self.assertEqual(reason, "Product is no longer published.")

    def test_product_not_reorderable_when_not_available(self):
        product = FakeProduct(
            pk=1,
            name="Apples",
            status=FakeProduct.Status.PUBLISHED,
            availability_status=FakeProduct.Availability_status.OUT_OF_STOCK,
        )

        ok, reason = _product_reorderable(product)

        self.assertFalse(ok)
        self.assertEqual(reason, "Product is not currently available.")


class InventoryReorderableTests(TestCase):
    def test_inventory_reorderable_when_not_expired(self):
        inventory = FakeInventory(
            pk=1,
            remaining_quantity=5,
            expiry_date=timezone.localdate() + timedelta(days=2),
            expiry_type=FakeInventory.ExpiryType.BEST_BEFORE,
        )

        ok, reason = _inventory_reorderable(inventory)

        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_inventory_not_reorderable_when_use_by_has_passed(self):
        inventory = FakeInventory(
            pk=1,
            remaining_quantity=5,
            expiry_date=timezone.localdate() - timedelta(days=1),
            expiry_type=FakeInventory.ExpiryType.USE_BY,
        )

        ok, reason = _inventory_reorderable(inventory)

        self.assertFalse(ok)
        self.assertEqual(reason, "Product batch has expired (use-by date passed).")

    def test_inventory_not_reorderable_when_best_before_has_passed(self):
        inventory = FakeInventory(
            pk=1,
            remaining_quantity=5,
            expiry_date=timezone.localdate() - timedelta(days=1),
            expiry_type=FakeInventory.ExpiryType.BEST_BEFORE,
        )

        ok, reason = _inventory_reorderable(inventory)

        self.assertFalse(ok)
        self.assertEqual(reason, "Product batch has expired.")


class ReorderOrderTests(TestCase):
    def setUp(self):
        self.user = SimpleNamespace(id=101)
        self.today = timezone.localdate()
        self.producer = FakeProducer(pk=201, name="Green Farm")

    def _build_item(
        self,
        *,
        product_status="PUB",
        availability_status="AV",
        remaining_quantity=10,
        expiry_days=3,
        expiry_type="BB",
        requested_quantity=2,
        original_unit_price=Decimal("10.00"),
        current_price=Decimal("10.00"),
    ):
        product = FakeProduct(
            pk=1,
            name="Apples",
            price=current_price,
            status=product_status,
            availability_status=availability_status,
        )
        inventory = FakeInventory(
            pk=11,
            remaining_quantity=remaining_quantity,
            expiry_date=self.today + timedelta(days=expiry_days),
            expiry_type=expiry_type,
        )
        return FakeOrderItem(
            product=product,
            inventory=inventory,
            producer=self.producer,
            quantity=requested_quantity,
            original_unit_price=original_unit_price,
        )

    @patch("orders.services.reorder_service.cart_add_item_for_owner")
    @patch("orders.services.reorder_service.get_order_detail_for_user")
    def test_reorder_adds_all_items_when_valid(self, mock_get_order, mock_cart_add):
        item1 = self._build_item(requested_quantity=2)
        item2 = self._build_item(
            requested_quantity=3,
            original_unit_price=Decimal("4.00"),
            current_price=Decimal("4.00"),
        )
        item2.product = FakeProduct(
            pk=2,
            name="Carrots",
            price=Decimal("4.00"),
            status=FakeProduct.Status.PUBLISHED,
            availability_status=FakeProduct.Availability_status.AVAILABLE,
        )
        item2.inventory = FakeInventory(
            pk=12,
            remaining_quantity=8,
            expiry_date=self.today + timedelta(days=5),
            expiry_type=FakeInventory.ExpiryType.BEST_BEFORE,
        )

        mock_get_order.return_value = FakeOrder([item1, item2])

        result = reorder_order(user=self.user, order_id=999)

        self.assertEqual(len(result["added_items"]), 2)
        self.assertEqual(len(result["unavailable_items"]), 0)
        self.assertEqual(len(result["quantity_adjusted_items"]), 0)
        self.assertEqual(len(result["price_changed_items"]), 0)
        self.assertEqual(result["message"], "All items successfully added to cart.")

        self.assertEqual(mock_cart_add.call_count, 2)
        mock_cart_add.assert_has_calls(
            [
                call(owner=ANY, inventory_id=11, quantity=2),
                call(owner=ANY, inventory_id=12, quantity=3),
            ],
            any_order=False,
        )

    @patch("orders.services.reorder_service.cart_add_item_for_owner")
    @patch("orders.services.reorder_service.get_order_detail_for_user")
    def test_reorder_skips_item_when_product_not_published(
        self, mock_get_order, mock_cart_add
    ):
        item = self._build_item(product_status=FakeProduct.Status.HIDDEN)
        mock_get_order.return_value = FakeOrder([item])

        result = reorder_order(user=self.user, order_id=999)

        self.assertEqual(len(result["added_items"]), 0)
        self.assertEqual(len(result["unavailable_items"]), 1)
        self.assertEqual(
            result["unavailable_items"][0]["reason"],
            "Product is no longer published.",
        )
        self.assertEqual(result["message"], "No items could be reordered.")
        mock_cart_add.assert_not_called()

    @patch("orders.services.reorder_service.cart_add_item_for_owner")
    @patch("orders.services.reorder_service.get_order_detail_for_user")
    def test_reorder_skips_item_when_product_not_available(
        self, mock_get_order, mock_cart_add
    ):
        item = self._build_item(
            availability_status=FakeProduct.Availability_status.OUT_OF_STOCK
        )
        mock_get_order.return_value = FakeOrder([item])

        result = reorder_order(user=self.user, order_id=999)

        self.assertEqual(len(result["added_items"]), 0)
        self.assertEqual(len(result["unavailable_items"]), 1)
        self.assertEqual(
            result["unavailable_items"][0]["reason"],
            "Product is not currently available.",
        )
        mock_cart_add.assert_not_called()

    @patch("orders.services.reorder_service.cart_add_item_for_owner")
    @patch("orders.services.reorder_service.get_order_detail_for_user")
    def test_reorder_skips_item_when_inventory_expired_use_by(
        self, mock_get_order, mock_cart_add
    ):
        item = self._build_item(
            expiry_days=-1,
            expiry_type=FakeInventory.ExpiryType.USE_BY,
        )
        mock_get_order.return_value = FakeOrder([item])

        result = reorder_order(user=self.user, order_id=999)

        self.assertEqual(len(result["added_items"]), 0)
        self.assertEqual(len(result["unavailable_items"]), 1)
        self.assertEqual(
            result["unavailable_items"][0]["reason"],
            "Product batch has expired (use-by date passed).",
        )
        mock_cart_add.assert_not_called()

    @patch("orders.services.reorder_service.cart_add_item_for_owner")
    @patch("orders.services.reorder_service.get_order_detail_for_user")
    def test_reorder_skips_item_when_inventory_out_of_stock(
        self, mock_get_order, mock_cart_add
    ):
        item = self._build_item(remaining_quantity=0)
        mock_get_order.return_value = FakeOrder([item])

        result = reorder_order(user=self.user, order_id=999)

        self.assertEqual(len(result["added_items"]), 0)
        self.assertEqual(len(result["unavailable_items"]), 1)
        self.assertEqual(
            result["unavailable_items"][0]["reason"],
            "Product batch is out of stock.",
        )
        mock_cart_add.assert_not_called()

    @patch("orders.services.reorder_service.cart_add_item_for_owner")
    @patch("orders.services.reorder_service.get_order_detail_for_user")
    def test_reorder_adjusts_quantity_when_stock_is_lower_than_original(
        self, mock_get_order, mock_cart_add
    ):
        item = self._build_item(requested_quantity=5, remaining_quantity=2)
        mock_get_order.return_value = FakeOrder([item])

        result = reorder_order(user=self.user, order_id=999)

        self.assertEqual(len(result["added_items"]), 1)
        self.assertEqual(result["added_items"][0]["added_quantity"], 2)

        self.assertEqual(len(result["quantity_adjusted_items"]), 1)
        self.assertEqual(result["quantity_adjusted_items"][0]["requested_quantity"], 5)
        self.assertEqual(result["quantity_adjusted_items"][0]["added_quantity"], 2)
        self.assertEqual(
            result["quantity_adjusted_items"][0]["reason"],
            "Quantity reduced due to limited stock.",
        )

        self.assertEqual(result["message"], "All items successfully added to cart.")
        mock_cart_add.assert_called_once_with(owner=ANY, inventory_id=11, quantity=2)

    @patch("orders.services.reorder_service.cart_add_item_for_owner")
    @patch("orders.services.reorder_service.get_order_detail_for_user")
    def test_reorder_collects_price_change_information(
        self, mock_get_order, mock_cart_add
    ):
        item = self._build_item(
            requested_quantity=2,
            original_unit_price=Decimal("7.50"),
            current_price=Decimal("9.00"),
        )
        mock_get_order.return_value = FakeOrder([item])

        result = reorder_order(user=self.user, order_id=999)

        self.assertEqual(len(result["price_changed_items"]), 1)
        self.assertEqual(
            result["price_changed_items"][0]["original_price"], Decimal("7.50")
        )
        self.assertEqual(
            result["price_changed_items"][0]["current_price"], Decimal("9.00")
        )
        self.assertEqual(len(result["added_items"]), 1)
        mock_cart_add.assert_called_once()

    @patch("orders.services.reorder_service.cart_add_item_for_owner")
    @patch("orders.services.reorder_service.get_order_detail_for_user")
    def test_reorder_handles_cart_service_validation_error(
        self, mock_get_order, mock_cart_add
    ):
        item = self._build_item(requested_quantity=2)
        mock_get_order.return_value = FakeOrder([item])
        mock_cart_add.side_effect = ValidationError("Not enough stock for cart merge.")

        result = reorder_order(user=self.user, order_id=999)

        self.assertEqual(len(result["added_items"]), 0)
        self.assertEqual(len(result["unavailable_items"]), 1)
        self.assertIn(
            "Not enough stock for cart merge.", result["unavailable_items"][0]["reason"]
        )
        self.assertEqual(result["message"], "No items could be reordered.")

    @patch("orders.services.reorder_service.cart_add_item_for_owner")
    @patch("orders.services.reorder_service.get_order_detail_for_user")
    def test_reorder_returns_partial_message_for_mixed_outcome(
        self, mock_get_order, mock_cart_add
    ):
        valid_item = self._build_item(requested_quantity=2)

        invalid_item = self._build_item(
            product_status=FakeProduct.Status.HIDDEN,
            requested_quantity=1,
        )
        invalid_item.product = FakeProduct(
            pk=2,
            name="Old Carrots",
            price=Decimal("5.00"),
            status=FakeProduct.Status.HIDDEN,
            availability_status=FakeProduct.Availability_status.AVAILABLE,
        )
        invalid_item.inventory = FakeInventory(
            pk=22,
            remaining_quantity=5,
            expiry_date=self.today + timedelta(days=5),
            expiry_type=FakeInventory.ExpiryType.BEST_BEFORE,
        )

        mock_get_order.return_value = FakeOrder([valid_item, invalid_item])

        result = reorder_order(user=self.user, order_id=999)

        self.assertEqual(len(result["added_items"]), 1)
        self.assertEqual(len(result["unavailable_items"]), 1)
        self.assertEqual(result["message"], "Reorder partially completed.")
        mock_cart_add.assert_called_once_with(owner=ANY, inventory_id=11, quantity=2)

    @patch("orders.services.reorder_service.get_order_detail_for_user")
    def test_reorder_propagates_order_does_not_exist_for_wrong_owner(
        self, mock_get_order
    ):
        mock_get_order.side_effect = Order.DoesNotExist

        with self.assertRaises(Order.DoesNotExist):
            reorder_order(user=self.user, order_id=999)
