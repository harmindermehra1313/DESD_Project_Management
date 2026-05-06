from decimal import Decimal, InvalidOperation

from django.utils import timezone

from notifications.models import Notification
from orders.models import ProducerOrderSummary
from django.contrib.auth import get_user_model
from django.db.models import Q

class NotificationService:
    """
    Central service for creating and updating notifications.

    Main rule:
    - use create() for event history, such as order status changes and refunds
    - use create_unique() for alert-style notifications where duplicates are unwanted
    """

    @staticmethod
    def _get_order_user(order):
        """
        Returns the user attached to an order.

        Supports:
        - order.user
        - order.customer.user

        Returns None for guest orders or orders without an attached customer user.
        """
        if not order:
            return None

        user = getattr(order, "user", None)
        if user:
            return user

        customer = getattr(order, "customer", None)
        if customer:
            return getattr(customer, "user", None)

        return None

    @staticmethod
    def _get_order_reference(order):
        """
        Returns the customer-facing order reference where available.
        Falls back to the database primary key.
        """
        if not order:
            return ""

        unique_reference = getattr(order, "unique_reference", None)

        if unique_reference:
            return unique_reference

        return str(order.pk)

    @staticmethod
    def _get_status_label(order, status_code):
        """
        Converts an order status code into its human-readable label.
        Falls back safely if choices are unavailable.
        """
        if not order:
            return str(status_code)

        try:
            choices = dict(order._meta.get_field("status").choices)
            return choices.get(status_code, status_code)
        except Exception:
            return str(status_code)

    @staticmethod
    def _format_money(amount):
        """
        Formats refund amounts consistently for customer messages.
        """
        try:
            return Decimal(str(amount)).quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError, ValueError):
            return amount

    @staticmethod
    def create(user, type, message, product=None, order=None):
        """
        Creates a new notification every time.

        Use this for:
        - order status changes
        - order cancellations
        - item cancellations
        - refunds
        - one-off customer event history
        """
        if not user:
            return None

        return Notification.objects.create(
            user=user,
            type=type,
            message=message,
            product=product,
            order=order,
        )

    @staticmethod
    def create_unique(user, type, message, product=None, order=None):
        """
        Creates a notification only if an unresolved duplicate does not already exist.

        Use this for:
        - low-stock alerts
        - product alerts
        - one-time order placed notifications
        - producer new-order alerts
        """
        if not user:
            return None

        existing = Notification.objects.filter(
            user=user,
            type=type,
            product=product,
            order=order,
            resolved_at__isnull=True,
        ).first()

        if existing:
            return existing

        return Notification.objects.create(
            user=user,
            type=type,
            message=message,
            product=product,
            order=order,
        )

    @staticmethod
    def notify_order_success(order):
        """
        Notifies a logged-in customer that an order has been placed successfully.

        Uses create_unique() because each order should only have one order-placed
        notification.
        """
        user = NotificationService._get_order_user(order)

        if not user:
            return None

        order_reference = NotificationService._get_order_reference(order)

        return NotificationService.create_unique(
            user=user,
            type=Notification.Type.ORDER_PLACED,
            order=order,
            message=f"Order #{order_reference} has been placed successfully.",
        )

    @staticmethod
    def notify_order_cancelled(order):
        """
        Notifies a customer that the full order has been cancelled.
        """
        user = NotificationService._get_order_user(order)

        if not user:
            return None

        order_reference = NotificationService._get_order_reference(order)

        return NotificationService.create(
            user=user,
            type=Notification.Type.ORDER_CANCELLED,
            order=order,
            message=f"Order #{order_reference} has been cancelled.",
        )

    @staticmethod
    def notify_order_item_cancelled(order, item, cancelled_quantity):
        """
        Notifies a customer that one item in an order has been cancelled.
        """
        user = NotificationService._get_order_user(order)

        if not user:
            return None

        order_reference = NotificationService._get_order_reference(order)
        product = getattr(item, "product", None)
        product_name = getattr(product, "name", "an item")

        return NotificationService.create(
            user=user,
            type=Notification.Type.ORDER_CANCELLED,
            order=order,
            product=product,
            message=(
                f"{cancelled_quantity} × {product_name} has been cancelled "
                f"from Order #{order_reference}."
            ),
        )

    @staticmethod
    def notify_order_status_changed(order, old_status, new_status):
        """
        Notifies a customer that the customer-facing order status has changed.

        Uses create(), not create_unique(), because the same order can have
        multiple valid status updates over time.
        """
        if old_status == new_status:
            return None

        user = NotificationService._get_order_user(order)

        if not user:
            return None

        order_reference = NotificationService._get_order_reference(order)
        old_label = NotificationService._get_status_label(order, old_status)
        new_label = NotificationService._get_status_label(order, new_status)

        return NotificationService.create(
            user=user,
            type=Notification.Type.ORDER_UPDATE,
            order=order,
            message=(
                f"Order #{order_reference} status changed "
                f"from {old_label} to {new_label}."
            ),
        )

    @staticmethod
    def notify_order_items_producer_status_changed(
        *,
        order,
        producer_summary,
        items,
        new_status,
    ):
        """
        Creates customer notifications for each active item affected by a producer
        fulfilment status change.

        Example:
        - 2 × Apples from Producer A in Order #123 has been shipped.
        """

        user = NotificationService._get_order_user(order)

        if not user:
            return []

        order_reference = NotificationService._get_order_reference(order)

        producer = getattr(producer_summary, "producer", None)
        producer_name = (
            getattr(producer, "business_name", None)
            or getattr(producer, "name", None)
            or str(producer)
            or "the producer"
        )

        status_message_by_code = {
            ProducerOrderSummary.Status.PACKAGED: "packed",
            ProducerOrderSummary.Status.READY_FOR_COLLECTION: "marked ready for collection",
            ProducerOrderSummary.Status.SHIPPED: "shipped",
            ProducerOrderSummary.Status.COMPLETED: "completed",
        }

        status_label = status_message_by_code.get(new_status, str(new_status).lower())

        notifications = []

        for item in items:
            product = getattr(item, "product", None)
            product_name = getattr(product, "name", "an item")

            active_quantity = max(
                getattr(item, "quantity", 0) - getattr(item, "cancelled_quantity", 0),
                0,
            )

            if active_quantity <= 0:
                continue

            quantity_text = f"{active_quantity} × {product_name}"

            notifications.append(
                NotificationService.create(
                    user=user,
                    type=Notification.Type.ORDER_UPDATE,
                    order=order,
                    product=product,
                    message=(
                        f"{quantity_text} from {producer_name} in "
                        f"Order #{order_reference} has been {status_label}."
                    ),
                )
            )

        return notifications

    @staticmethod
    def notify_refund_processed(order, amount):
        """
        Notifies a customer that a refund has been processed.
        """
        user = NotificationService._get_order_user(order)

        if not user:
            return None

        order_reference = NotificationService._get_order_reference(order)
        formatted_amount = NotificationService._format_money(amount)

        return NotificationService.create(
            user=user,
            type=Notification.Type.REFUND,
            order=order,
            message=(
                f"A refund of £{formatted_amount} has been processed "
                f"for Order #{order_reference}."
            ),
        )

    @staticmethod
    def resolve_for_product(product, type):
        """
        Marks unresolved product notifications of a given type as resolved.
        """
        Notification.objects.filter(
            product=product,
            type=type,
            resolved_at__isnull=True,
        ).update(resolved_at=timezone.now())

    @staticmethod
    def mark_read(notification):
        """
        Marks one notification as read.
        """
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])

    @staticmethod
    def mark_all_read(user):
        """
        Marks all notifications for one user as read.
        """
        if not user:
            return 0

        return Notification.objects.filter(
            user=user,
            read_at__isnull=True,
        ).update(read_at=timezone.now())

    @staticmethod
    def _get_producer_user(producer):
        """
        Returns the user attached to a producer profile.

        Supports common project structures:
        - producer.user
        - producer.owner
        - producer.account
        - producer.profile.user
        """
        if not producer:
            return None

        user = getattr(producer, "user", None)
        if user:
            return user

        owner = getattr(producer, "owner", None)
        if owner:
            return owner

        account = getattr(producer, "account", None)
        if account:
            return account

        profile = getattr(producer, "profile", None)
        if profile:
            return getattr(profile, "user", None)

        return None

    @staticmethod
    def _get_producer_display_name(producer):
        """
        Returns a readable producer name for notifications.
        """
        if not producer:
            return "this producer"

        return (
            getattr(producer, "business_name", None)
            or getattr(producer, "name", None)
            or str(producer)
            or "this producer"
        )

    @staticmethod
    def notify_producer_order_cancelled_by_customer(*, order, producer_summary):
        """
        Notifies a producer that the customer cancelled the full order,
        or the producer's section of the order is now cancelled.
        """
        producer = getattr(producer_summary, "producer", None)
        user = NotificationService._get_producer_user(producer)

        if not user:
            return None

        order_reference = NotificationService._get_order_reference(order)
        producer_name = NotificationService._get_producer_display_name(producer)

        return NotificationService.create(
            user=user,
            type=Notification.Type.ORDER_CANCELLED,
            order=order,
            message=(
                f"Customer cancelled Order #{order_reference}. "
                f"The order section for {producer_name} is now cancelled. "
                f"No preparation is required."
            ),
        )

    @staticmethod
    def notify_producer_order_item_cancelled_by_customer(
        *,
        order,
        item,
        cancelled_quantity,
        producer_summary=None,
    ):
        """
        Notifies a producer that the customer cancelled one item from an order.
        """
        producer = getattr(item, "producer", None)

        if producer is None and producer_summary is not None:
            producer = getattr(producer_summary, "producer", None)

        user = NotificationService._get_producer_user(producer)

        if not user:
            return None

        order_reference = NotificationService._get_order_reference(order)
        product = getattr(item, "product", None)
        product_name = getattr(product, "name", "an item")

        message = (
            f"Customer cancelled {cancelled_quantity} × {product_name} "
            f"from Order #{order_reference}."
        )

        if (
            producer_summary is not None
            and producer_summary.status == ProducerOrderSummary.Status.CANCELLED
        ):
            message += (
                " This producer order section is now cancelled because "
                "no active items remain."
            )
        else:
            message += " Please update preparation for this order section."

        return NotificationService.create(
            user=user,
            type=Notification.Type.ORDER_CANCELLED,
            order=order,
            product=product,
            message=message,
        )
    
    @staticmethod
    def _get_admin_users():
        """
        Returns active staff users who should receive admin dashboard notifications.
        """
        User = get_user_model()

        return User.objects.filter(
            is_active=True,
            is_staff=True,
        )

    @staticmethod
    def create_for_admins(type, message, product=None, order=None):
        """
        Creates a fresh notification for every active staff user.

        Important:
        Moderation events should create fresh notifications because the same
        review or producer response can become flagged again after a previous
        moderation decision.
        """
        notifications = []

        for admin_user in NotificationService._get_admin_users():
            notifications.append(
                Notification.objects.create(
                    user=admin_user,
                    type=type,
                    message=message,
                    product=product,
                    order=order,
                )
            )

        return notifications

    @staticmethod
    def _get_review_flagged_message(review):
        product = getattr(review, "product", None)
        product_name = getattr(product, "name", "a product")

        return f"Customer review #{review.id} for {product_name} was flagged for moderation."

    @staticmethod
    def _get_legacy_review_flagged_message(review):
        product = getattr(review, "product", None)
        product_name = getattr(product, "name", "a product")

        return f"Customer review for {product_name} was flagged for moderation."

    @staticmethod
    def _get_producer_response_flagged_message(response):
        review = getattr(response, "review", None)
        product = getattr(review, "product", None)
        product_name = getattr(product, "name", "a product")

        return f"Producer response #{response.id} for {product_name} was flagged for moderation."

    @staticmethod
    def _get_legacy_producer_response_flagged_message(response):
        review = getattr(response, "review", None)
        product = getattr(review, "product", None)
        product_name = getattr(product, "name", "a product")

        return f"Producer response for {product_name} was flagged for moderation."
    @staticmethod
    def _get_review_notification_type():
        """
        Uses REVIEW_UPDATE when available.
        Falls back safely for older notification models.
        """
        return getattr(
            Notification.Type,
            "REVIEW_UPDATE",
            Notification.Type.REVIEW_FLAGGED,
        )

    @staticmethod
    def _get_review_customer_user(review):
        customer = getattr(review, "customer", None)

        if customer:
            return getattr(customer, "user", None)

        order = getattr(review, "order", None)
        return NotificationService._get_order_user(order)

    @staticmethod
    def _get_review_product(review):
        return getattr(review, "product", None)

    @staticmethod
    def _get_review_order(review):
        return getattr(review, "order", None)

    @staticmethod
    def _get_review_product_name(review):
        product = NotificationService._get_review_product(review)
        return getattr(product, "name", None) or "a product"

    @staticmethod
    def _get_review_producer(review):
        product = NotificationService._get_review_product(review)
        return getattr(product, "producer", None)

    @staticmethod
    def _notify_customer_and_producer_for_review(
        review,
        *,
        customer_message,
        producer_message,
    ):
        """
        Creates one review-event notification for the customer and one for the
        producer who owns the reviewed product.
        """
        product = NotificationService._get_review_product(review)
        order = NotificationService._get_review_order(review)
        notification_type = NotificationService._get_review_notification_type()

        customer_user = NotificationService._get_review_customer_user(review)
        producer = NotificationService._get_review_producer(review)
        producer_user = NotificationService._get_producer_user(producer)

        notifications = []

        if customer_user:
            notifications.append(
                NotificationService.create(
                    user=customer_user,
                    type=notification_type,
                    product=product,
                    order=order,
                    message=customer_message,
                )
            )

        if producer_user and producer_user != customer_user:
            notifications.append(
                NotificationService.create(
                    user=producer_user,
                    type=notification_type,
                    product=product,
                    order=order,
                    message=producer_message,
                )
            )

        return notifications

    @staticmethod
    def notify_review_published_after_submission(review):
        product_name = NotificationService._get_review_product_name(review)

        return NotificationService._notify_customer_and_producer_for_review(
            review,
            customer_message=(
                f"Review for {product_name} has been published successfully."
            ),
            producer_message=(
                f"New customer review received for {product_name}."
            ),
        )

    @staticmethod
    def notify_review_flagged_after_submission(review):
        product_name = NotificationService._get_review_product_name(review)

        return NotificationService._notify_customer_and_producer_for_review(
            review,
            customer_message=(
                f"Review for {product_name} has been sent for admin moderation."
            ),
            producer_message=(
                f"A customer review for {product_name} is waiting for admin moderation "
                "before publication."
            ),
        )

    @staticmethod
    def notify_review_flag_rejected_and_published(review):
        """
        Used when an admin rejects the moderation flag and publishes the review.
        """
        product_name = NotificationService._get_review_product_name(review)

        return NotificationService._notify_customer_and_producer_for_review(
            review,
            customer_message=(
                f"Review for {product_name} was approved and published after moderation."
            ),
            producer_message=(
                f"Customer review for {product_name} was approved and is now visible."
            ),
        )

    @staticmethod
    def notify_review_kept_flagged_after_moderation(review):
        product_name = NotificationService._get_review_product_name(review)

        return NotificationService._notify_customer_and_producer_for_review(
            review,
            customer_message=(
                f"Review for {product_name} remains under admin moderation."
            ),
            producer_message=(
                f"Customer review for {product_name} remains under admin moderation."
            ),
        )

    @staticmethod
    def notify_review_removed_after_moderation(review):
        product_name = NotificationService._get_review_product_name(review)

        return NotificationService._notify_customer_and_producer_for_review(
            review,
            customer_message=(
                f"Review for {product_name} was removed after admin moderation."
            ),
            producer_message=(
                f"Customer review for {product_name} was removed after admin moderation."
            ),
        )
    @staticmethod
    def _clean_notification_reason(reason, *, fallback="No reason was provided."):
        cleaned_reason = " ".join(str(reason or "").split())

        if not cleaned_reason:
            return fallback

        if len(cleaned_reason) > 260:
            return f"{cleaned_reason[:257]}..."

        return cleaned_reason

    @staticmethod
    def _get_producer_response_review(response):
        return getattr(response, "review", None)

    @staticmethod
    def _get_producer_response_product(response):
        review = NotificationService._get_producer_response_review(response)

        if review is None:
            return None

        return getattr(review, "product", None)

    @staticmethod
    def _get_producer_response_order(response):
        review = NotificationService._get_producer_response_review(response)

        if review is None:
            return None

        return getattr(review, "order", None)

    @staticmethod
    def _get_producer_response_product_name(response):
        product = NotificationService._get_producer_response_product(response)
        return getattr(product, "name", None) or "a product"

    @staticmethod
    def _get_producer_response_user(response):
        responder = getattr(response, "responder", None)

        if responder:
            return responder

        review = NotificationService._get_producer_response_review(response)

        if review is None:
            return None

        product = getattr(review, "product", None)
        producer = getattr(product, "producer", None)

        return NotificationService._get_producer_user(producer)

    @staticmethod
    def _get_producer_response_customer_user(response):
        review = NotificationService._get_producer_response_review(response)

        if review is None:
            return None

        return NotificationService._get_review_customer_user(review)

    @staticmethod
    def _notify_producer_response_users(
        response,
        *,
        producer_message,
        customer_message=None,
    ):
        """
        Creates notification records for producer-response moderation events.

        Producer always receives the producer-facing message.
        Customer receives a message only when one is provided.
        """
        notification_type = NotificationService._get_review_notification_type()
        product = NotificationService._get_producer_response_product(response)
        order = NotificationService._get_producer_response_order(response)

        producer_user = NotificationService._get_producer_response_user(response)
        customer_user = NotificationService._get_producer_response_customer_user(response)

        notifications = []

        if producer_user:
            notifications.append(
                NotificationService.create(
                    user=producer_user,
                    type=notification_type,
                    product=product,
                    order=order,
                    message=producer_message,
                )
            )

        if customer_message and customer_user and customer_user != producer_user:
            notifications.append(
                NotificationService.create(
                    user=customer_user,
                    type=notification_type,
                    product=product,
                    order=order,
                    message=customer_message,
                )
            )

        return notifications

    @staticmethod
    def notify_producer_response_published_after_submission(response):
        product_name = NotificationService._get_producer_response_product_name(response)

        return NotificationService._notify_producer_response_users(
            response,
            producer_message=(
                f"Your response for {product_name} has been published successfully."
            ),
            customer_message=(
                f"The producer has replied to your review for {product_name}."
            ),
        )

    @staticmethod
    def notify_producer_response_flagged_after_submission(response):
        product_name = NotificationService._get_producer_response_product_name(response)
        reason = NotificationService._clean_notification_reason(
            getattr(response, "moderation_notes", ""),
            fallback="Automatic moderation requires admin review.",
        )

        return NotificationService._notify_producer_response_users(
            response,
            producer_message=(
                f"Your response for {product_name} has been sent for admin moderation. "
                f"Reason: {reason}"
            ),
            customer_message=None,
        )

    @staticmethod
    def notify_producer_response_approved_after_moderation(response):
        product_name = NotificationService._get_producer_response_product_name(response)
        reason = NotificationService._clean_notification_reason(
            getattr(response, "moderation_notes", ""),
            fallback="Admin approved the response after moderation.",
        )

        return NotificationService._notify_producer_response_users(
            response,
            producer_message=(
                f"Your response for {product_name} was approved and published. "
                f"Reason: {reason}"
            ),
            customer_message=(
                f"The producer response for {product_name} was approved and is now visible."
            ),
        )

    @staticmethod
    def notify_producer_response_kept_flagged_after_moderation(response):
        product_name = NotificationService._get_producer_response_product_name(response)
        reason = NotificationService._clean_notification_reason(
            getattr(response, "moderation_notes", ""),
            fallback="Admin kept the response flagged for further moderation.",
        )

        return NotificationService._notify_producer_response_users(
            response,
            producer_message=(
                f"Your response for {product_name} is still under admin moderation. "
                f"Reason: {reason}"
            ),
            customer_message=None,
        )

    @staticmethod
    def notify_producer_response_removed_after_moderation(response):
        product_name = NotificationService._get_producer_response_product_name(response)
        reason = NotificationService._clean_notification_reason(
            getattr(response, "moderation_notes", ""),
            fallback="Admin removed the response after moderation.",
        )

        return NotificationService._notify_producer_response_users(
            response,
            producer_message=(
                f"Your response for {product_name} was removed after admin moderation. "
                f"Reason: {reason}"
            ),
            customer_message=None,
        )
    @staticmethod
    def notify_admin_review_flagged(review):
        """
        Creates a fresh admin notification when a customer review is flagged.
        """
        product = getattr(review, "product", None)

        return NotificationService.create_for_admins(
            type=Notification.Type.REVIEW_FLAGGED,
            product=product,
            message=NotificationService._get_review_flagged_message(review),
        )

    @staticmethod
    def notify_admin_producer_response_flagged(response):
        """
        Creates a fresh admin notification when a producer response is flagged.
        """
        review = getattr(response, "review", None)
        product = getattr(review, "product", None)

        return NotificationService.create_for_admins(
            type=Notification.Type.REVIEW_FLAGGED,
            product=product,
            message=NotificationService._get_producer_response_flagged_message(response),
        )

    @staticmethod
    def resolve_admin_review_flagged_notifications(review):
        """
        Resolves unresolved admin notifications for one moderated customer review.
        Includes the previous legacy message format so existing notifications
        can still be resolved.
        """
        product = getattr(review, "product", None)

        return Notification.objects.filter(
            type=Notification.Type.REVIEW_FLAGGED,
            product=product,
            resolved_at__isnull=True,
        ).filter(
            Q(message=NotificationService._get_review_flagged_message(review))
            | Q(message=NotificationService._get_legacy_review_flagged_message(review))
        ).update(resolved_at=timezone.now())

    @staticmethod
    def resolve_admin_producer_response_flagged_notifications(response):
        """
        Resolves unresolved admin notifications for one moderated producer response.
        Includes the previous legacy message format so existing notifications
        can still be resolved.
        """
        review = getattr(response, "review", None)
        product = getattr(review, "product", None)

        return Notification.objects.filter(
            type=Notification.Type.REVIEW_FLAGGED,
            product=product,
            resolved_at__isnull=True,
        ).filter(
            Q(message=NotificationService._get_producer_response_flagged_message(response))
            | Q(message=NotificationService._get_legacy_producer_response_flagged_message(response))
        ).update(resolved_at=timezone.now())