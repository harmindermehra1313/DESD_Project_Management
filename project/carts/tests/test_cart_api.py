from __future__ import annotations

from decimal import Decimal

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient


class TestCartAPI_TC006(TestCase):
    """
    TC-006 proof: one end-to-end API test that follows all 12 steps for:
      Organic Carrots (2kg -> later 3kg)
      Fresh Milk (3L)

    Notes:
    - Uses existing endpoints:
        GET    /api/cart/
        POST   /api/cart/items/
        PATCH  /api/cart/items/<product_id>/
    - "confirmation message" is interpreted as 201 Created + returned cart line payload.
    - "cart persists during browsing session" is validated by cart id staying the same.
    """

    @staticmethod
    def _d(v: str) -> Decimal:
        return Decimal(v)

    def _make_product(self, *, name: str, price: Decimal, unit: str, stock: Decimal):
        """
        Create a Product robustly (project schemas vary).
        Prefers model_bakery if available, otherwise uses ORM with best-effort field filling.
        """
        Product = apps.get_model("products", "Product")

       

        try:
            from model_bakery import baker  

            kwargs = {
                "name": name,
                "price": price,
                "unit": unit,
                "stock_quantity": stock,
            }
          

            return baker.make(Product, **kwargs)
        except Exception:
            pass

        
        field_names = {f.name for f in Product._meta.get_fields()}
        create_kwargs = {}

        if "name" in field_names:
            create_kwargs["name"] = name
        if "price" in field_names:
            create_kwargs["price"] = price
        if "unit" in field_names:
            create_kwargs["unit"] = unit
        if "stock_quantity" in field_names:
            create_kwargs["stock_quantity"] = stock



        # Fill common required fields if present
        if "description" in field_names and "description" not in create_kwargs:
            create_kwargs["description"] = f"{name} description"
        if "is_active" in field_names and "is_active" not in create_kwargs:
            create_kwargs["is_active"] = True

        # If category is required, attempt to create one
        if "category" in field_names and "category" not in create_kwargs:
            try:
                Category = apps.get_model("products", "Category")
                cat_fields = {f.name for f in Category._meta.get_fields()}
                cat_kwargs = {}
                if "name" in cat_fields:
                    cat_kwargs["name"] = "Test Category"
                category = Category.objects.create(**cat_kwargs) if cat_kwargs else Category.objects.create()
                create_kwargs["category"] = category
            except Exception:
              
                pass

        return Product.objects.create(**create_kwargs)

    def test_tc006_add_modify_view_cart_end_to_end(self):
        client = APIClient()

        # Preconditions: Customer is logged in
        User = get_user_model()
        create_kwargs = {
        "email": "tc006_customer@example.com",
        "password": "pass12345",
        }
        user_field_names = {f.name for f in User._meta.get_fields()}
        if "username" in user_field_names:
            create_kwargs["username"] = "tc006_customer"
        user = User.objects.create_user(**create_kwargs)
        
        client.force_authenticate(user=user)

        # Preconditions: Multiple products available for purchase
        carrots_price = self._d("1.50")
        milk_price = self._d("0.80")

        carrots = self._make_product(
            name="Organic Carrots",
            price=carrots_price,
            unit="kg",
            stock=self._d("100.00"),
        )
        milk = self._make_product(
            name="Fresh Milk",
            price=milk_price,
            unit="litre",
            stock=self._d("100.00"),
        )

        # --- Step 1-2: Browse/search + view details (API equivalent: product exists; optional GET product) ---
        self.assertIsNotNone(carrots.id)
        self.assertIsNotNone(milk.id)

        # --- Step 3-4: Select quantity 2kg and Add to Cart ---
        r = client.post(
            "/api/cart/items/",
            data={"product_id": carrots.id, "quantity": "2.00"},
            format="json",
        )
        # --- Step 5: Observe confirmation message (API: 201 + payload for cart line) ---
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["product_id"], carrots.id)
        self.assertEqual(Decimal(str(r.data["quantity"])), self._d("2.00"))
        # unit_price should be snapshotted from product.price
        self.assertEqual(Decimal(str(r.data["unit_price"])), carrots_price)
        # line_total should exist
        self.assertEqual(Decimal(str(r.data["line_total"])), carrots_price * self._d("2.00"))
        carrots_line_id = r.data["id"]

        # --- The cart exists now; capture cart id for persistence check ---
        r_cart = client.get("/api/cart/")
        self.assertEqual(r_cart.status_code, 200)
        cart_id_initial = r_cart.data["id"]

        # --- Step 6-8: Navigate to Fresh Milk, quantity 3L, Add to Cart ---
        r = client.post(
            "/api/cart/items/",
            data={"product_id": milk.id, "quantity": "3.00"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["product_id"], milk.id)
        self.assertEqual(Decimal(str(r.data["quantity"])), self._d("3.00"))
        self.assertEqual(Decimal(str(r.data["unit_price"])), milk_price)
        self.assertEqual(Decimal(str(r.data["line_total"])), milk_price * self._d("3.00"))
        milk_line_id = r.data["id"]

        # --- Step 9: Click cart icon to view contents (API: GET /api/cart/) ---
        r = client.get("/api/cart/")
        self.assertEqual(r.status_code, 200)

        # Persist during browsing session (same logged-in customer cart)
        self.assertEqual(r.data["id"], cart_id_initial)

        # --- Step 10: Verify both products appear with correct quantities and prices ---
        items = r.data["items"]
        self.assertEqual(len(items), 2)

        # "Cart icon displays item count" => item_count on cart serializer
        self.assertEqual(r.data["item_count"], 2)

        # Index by product_id for stable assertions
        by_pid = {it["product_id"]: it for it in items}

        self.assertIn(carrots.id, by_pid)
        self.assertIn(milk.id, by_pid)

        self.assertEqual(Decimal(str(by_pid[carrots.id]["quantity"])), self._d("2.00"))
        self.assertEqual(Decimal(str(by_pid[carrots.id]["unit_price"])), carrots_price)
        self.assertEqual(Decimal(str(by_pid[carrots.id]["line_total"])), carrots_price * self._d("2.00"))

        self.assertEqual(Decimal(str(by_pid[milk.id]["quantity"])), self._d("3.00"))
        self.assertEqual(Decimal(str(by_pid[milk.id]["unit_price"])), milk_price)
        self.assertEqual(Decimal(str(by_pid[milk.id]["line_total"])), milk_price * self._d("3.00"))

        # Multi-vendor awareness: product mini snapshot includes producer_name key
        self.assertIn("product", by_pid[carrots.id])
        self.assertIn("producer_name", by_pid[carrots.id]["product"])

        # Totals accurate
        expected_total = carrots_price * self._d("2.00") + milk_price * self._d("3.00")
        self.assertEqual(Decimal(str(r.data["total_price"])), expected_total)

        # --- Step 11: Modify quantity of Organic Carrots to 3kg ---
        r = client.patch(
            f"/api/cart/items/{carrots.id}/",
            data={"quantity": "3.00"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["product_id"], carrots.id)
        self.assertEqual(Decimal(str(r.data["quantity"])), self._d("3.00"))
        # Price snapshot must NOT change when updating qty
        self.assertEqual(Decimal(str(r.data["unit_price"])), carrots_price)

        # --- Step 12: Observe updated total price ---
        r = client.get("/api/cart/")
        self.assertEqual(r.status_code, 200)
        items = r.data["items"]
        by_pid = {it["product_id"]: it for it in items}

        expected_total_after = carrots_price * self._d("3.00") + milk_price * self._d("3.00")
        self.assertEqual(Decimal(str(by_pid[carrots.id]["line_total"])), carrots_price * self._d("3.00"))
        self.assertEqual(Decimal(str(r.data["total_price"])), expected_total_after)

        # Extra: sanity checks that the original line ids are still present (no duplication)
        line_ids = {it["id"] for it in items}
        self.assertIn(carrots_line_id, line_ids)
        self.assertIn(milk_line_id, line_ids)