from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django_q.tasks import async_task
from .models import Product
from orders.models import RecurringOrderItem

@receiver(pre_save, sender=Product)
def track_price_change(sender, instance, **kwargs):
    """Store the original price before saving to compare later."""
    if instance.pk:
        try:
            old_product = Product.objects.get(pk=instance.pk)
            instance._old_price = old_product.price
        except Product.DoesNotExist:
            instance._old_price = None
    else:
        instance._old_price = None

@receiver(post_save, sender=Product)
def notify_recurring_order_price_change(sender, instance, created, **kwargs):
    """If the price changed, email anyone who has this in an active recurring order."""
    if not created and hasattr(instance, '_old_price') and instance._old_price is not None:
        if instance.price != instance._old_price:
            # Find all active recurring orders containing this product
            items = RecurringOrderItem.objects.filter(
                product=instance, 
                recurring_order__status="ACTIVE"
            ).select_related('recurring_order__user')
            
            # Use a set to avoid emailing the same user twice if they have multiple recurring orders
            users_emailed = set()
            for item in items:
                user = item.recurring_order.user
                if user.email and user.email not in users_emailed:
                    async_task(
                        'orders.tasks.send_order_email',
                        subject="Price Update on Your Recurring Order",
                        message=(
                            f"Hi {user.name},\n\n"
                            f"The unit price for {instance.name} has been updated from "
                            f"£{instance._old_price} to £{instance.price}.\n"
                            f"This new price will apply to your upcoming recurring orders."
                        ),
                        recipient=user.email
                    )
                    users_emailed.add(user.email)