from django.core.exceptions import ValidationError
from django.db import transaction
from model_bakery import baker

from orders.models import Order
from reviews.models import Review

# docker compose exec web python manage.py shell
# exec(open("reviews/tests/test_review_model.py").read())
# run_review_model_shell_tests()


def run_review_model_shell_tests():

    def print_divider(title):
        print("\n" + "=" * 90)
        print(title)
        print("=" * 90)

    def build_review(**overrides):
        data = {
            "product": product,
            "customer": customer,
            "order": completed_order,
            "order_item": completed_order_item,
            "rating": 5,
            "title": "Shell test review",
            "text": "Shell test review text",
            "anonymous": True,
        }
        data.update(overrides)
        return Review(**data)

    def run_case(case_name, review, should_pass, expected_field=None, expected_text=None):
        print(f"\nCASE: {case_name}")

        try:
            review.save()

            if should_pass:
                print("RESULT: PASS")
                print(f"OUTPUT: Review saved successfully. review_id={review.pk}")
            else:
                print("RESULT: FAIL")
                print("OUTPUT: Review saved unexpectedly, but this case should have failed.")

        except ValidationError as exc:
            print("OUTPUT: ValidationError raised")
            print(f"DETAILS: {exc.message_dict}")

            if should_pass:
                print("RESULT: FAIL")
                print("OUTPUT: This case should have passed, but validation failed.")
                return

            field_ok = expected_field is None or expected_field in exc.message_dict
            text_ok = True

            if expected_text is not None:
                text_ok = any(
                    expected_text in message
                    for messages in exc.message_dict.values()
                    for message in messages
                )

            if field_ok and text_ok:
                print("RESULT: PASS")
                print("OUTPUT: Validation failed exactly where expected.")
            else:
                print("RESULT: FAIL")
                print("OUTPUT: Validation failed, but not with the expected field/message.")

        except Exception as exc:
            print("RESULT: FAIL")
            print(f"OUTPUT: Unexpected exception type: {type(exc).__name__}")
            print(f"DETAILS: {exc}")

    with transaction.atomic():
        try:
            print_divider("SETTING UP TEMPORARY TEST DATA")

            # Core actors
            customer = baker.make("accounts.Customer")
            other_customer = baker.make("accounts.Customer")

            # Products
            product = baker.make("products.Product")
            other_product = baker.make("products.Product")

            # Completed order for the main customer with the target product
            completed_order = baker.make(
                "orders.Order",
                user=customer.user,
                status=Order.Status.COMPLETED,
            )
            completed_order_item = baker.make(
                "orders.OrderItem",
                order=completed_order,
                product=product,
            )

            # Another item in the same completed order, but for a different product
            completed_order_other_product_item = baker.make(
                "orders.OrderItem",
                order=completed_order,
                product=other_product,
            )

            # Another completed order for the same customer
            another_completed_order = baker.make(
                "orders.Order",
                user=customer.user,
                status=Order.Status.COMPLETED,
            )
            another_completed_order_item = baker.make(
                "orders.OrderItem",
                order=another_completed_order,
                product=product,
            )

            # Completed order that does not contain the target product
            completed_order_without_target_product = baker.make(
                "orders.Order",
                user=customer.user,
                status=Order.Status.COMPLETED,
            )
            unrelated_item_in_other_completed_order = baker.make(
                "orders.OrderItem",
                order=completed_order_without_target_product,
                product=other_product,
            )

            # Completed order for a different customer
            other_customer_completed_order = baker.make(
                "orders.Order",
                user=other_customer.user,
                status=Order.Status.COMPLETED,
            )
            other_customer_completed_order_item = baker.make(
                "orders.OrderItem",
                order=other_customer_completed_order,
                product=product,
            )

            # Non-completed order for the main customer
            non_completed_status = next(
                value
                for value, _label in Order.Status.choices
                if value != Order.Status.COMPLETED
            )
            non_completed_order = baker.make(
                "orders.Order",
                user=customer.user,
                status=non_completed_status,
            )
            non_completed_order_item = baker.make(
                "orders.OrderItem",
                order=non_completed_order,
                product=product,
            )

            print("Temporary data created successfully.")
            print(f"customer_id={customer.id}")
            print(f"customer_user_id={customer.user_id}")
            print(f"other_customer_id={other_customer.id}")
            print(f"other_customer_user_id={other_customer.user_id}")
            print(f"product_id={product.id}")
            print(f"other_product_id={other_product.id}")
            print(f"completed_order_id={completed_order.id}")
            print(f"completed_order_item_id={completed_order_item.id}")
            print(f"another_completed_order_id={another_completed_order.id}")
            print(f"another_completed_order_item_id={another_completed_order_item.id}")
            print(f"completed_order_without_target_product_id={completed_order_without_target_product.id}")
            print(f"other_customer_completed_order_id={other_customer_completed_order.id}")
            print(f"non_completed_order_id={non_completed_order.id}")
            print(f"non_completed_status_used={non_completed_status}")

            # Optional sanity check:
            # this matches the clean() implementation you currently use:
            # self.order.items.filter(product_id=self.product_id).exists()
            if not hasattr(completed_order, "items"):
                print("\nWARNING:")
                print("Order object has no 'items' related name.")
                print("If your Review.clean() uses self.order.items.filter(...),")
                print("update that line to the real related_name on OrderItem.order before trusting these checks.")

            # ----------------------------------------------------------------------------------
            # feat (Review Model): link reviews to the originating fulfilled order or order item
            # ----------------------------------------------------------------------------------
            print_divider("feat (Review Model): link reviews to the originating fulfilled order or order item")

            run_case(
                case_name="review saves when order and order_item match the same completed purchase",
                review=build_review(
                    title="Linkage happy path",
                    text="Correct completed order and matching order item",
                ),
                should_pass=True,
            )

            run_case(
                case_name="review fails when order_item belongs to a different order",
                review=build_review(
                    order=completed_order,
                    order_item=another_completed_order_item,
                    title="Wrong order item order linkage",
                    text="Order item comes from another completed order",
                ),
                should_pass=False,
                expected_field="order_item",
                expected_text="Selected order item does not belong to the selected order.",
            )

            run_case(
                case_name="review fails when order_item product does not match the reviewed product",
                review=build_review(
                    order=completed_order,
                    order_item=completed_order_other_product_item,
                    product=product,
                    title="Wrong order item product linkage",
                    text="Order item points to a different product",
                ),
                should_pass=False,
                expected_field="product",
                expected_text="Selected order item does not match the reviewed product.",
            )

            # ----------------------------------------------------------------------------
            # feat (Review Model): restrict reviews to verified purchased products
            # ----------------------------------------------------------------------------
            print_divider("feat (Review Model): restrict reviews to verified purchased products")

            run_case(
                case_name="review saves when completed order contains the product even without order_item",
                review=build_review(
                    order=completed_order,
                    order_item=None,
                    product=product,
                    title="Verified purchase via order only",
                    text="No order_item linked, but product exists in completed order",
                ),
                should_pass=True,
            )

            run_case(
                case_name="review fails when completed order does not contain the reviewed product",
                review=build_review(
                    order=completed_order_without_target_product,
                    order_item=None,
                    product=product,
                    title="Product not purchased in this order",
                    text="Completed order exists but target product is not in it",
                ),
                should_pass=False,
                expected_field="product",
                expected_text="You can only review products that were delivered in this order.",
            )

            run_case(
                case_name="review fails when the linked order belongs to another customer",
                review=build_review(
                    customer=customer,
                    order=other_customer_completed_order,
                    order_item=other_customer_completed_order_item,
                    product=product,
                    title="Other customer's order",
                    text="Attempt to review using another customer's completed order",
                ),
                should_pass=False,
                expected_field="customer",
                expected_text="You can only review products from your own delivered orders.",
            )

            # ------------------------------------------------------------------------
            # feat (Review Model): restrict review submission to delivered orders
            # ------------------------------------------------------------------------
            print_divider("feat (Review Model): restrict review submission to delivered orders")

            run_case(
                case_name="review fails when the linked order is not completed",
                review=build_review(
                    order=non_completed_order,
                    order_item=non_completed_order_item,
                    product=product,
                    title="Non-completed order review attempt",
                    text="Order status is not completed",
                ),
                should_pass=False,
                expected_field="order",
                expected_text="Reviews can only be submitted for delivered orders.",
            )

            run_case(
                case_name="review saves when the linked order is completed",
                review=build_review(
                    order=completed_order,
                    order_item=completed_order_item,
                    product=product,
                    title="Completed order review attempt",
                    text="Order status is completed",
                ),
                should_pass=True,
            )

            print_divider("SUMMARY")
            print("All shell validation checks finished.")
            print("The transaction will now be rolled back, so no test data will remain.")

        finally:
            transaction.set_rollback(True)