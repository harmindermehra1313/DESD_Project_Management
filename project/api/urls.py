from rest_framework.routers import DefaultRouter


from api.views.accounts import (
    UserViewSet,
    AddressViewSet,
    ProducerViewSet,
    AdminViewSet,
    CustomerViewSet,
)
from api.views.admin_records import (
    SecurityLogViewSet,
    AdminPostViewSet,
    ModerationLogViewSet,
    DistanceRecordViewSet,
)
from api.views.community import (
    RecipeViewSet,
    RecipeProductViewSet,
    FarmStoryViewSet,
    FavouriteRecipeViewSet,
)
from api.views.notifications import (
    NotificationViewSet,
    RecallNoticeViewSet,
    RecallNotificationViewSet,
    TraceabilityRecordViewSet,
)
from api.views.orders import (
    OrderViewSet,
    OrderItemViewSet,
    ProducerOrderSummaryViewSet,
    ProducerOrderStatusHistoryViewSet,
    RecurringOrderViewSet,
    RecurringOrderItemViewSet,
    CheckoutAPIView
)
from api.views.payments import (
    PaymentViewSet,
    ProducerSettlementViewSet,
    SettlementLineItemViewSet,
)
from api.views.products import (
    CategoryViewSet,
    ProductViewSet,
    WholesalePriceViewSet,
    ProductUpdateHistoryViewSet,
    AllergenViewSet,
    ProductAllergenViewSet,
)
from api.views.reviews import (
    ReviewViewSet,
    ReviewResponseViewSet,
)

from api.views.carts import CartViewSet


from django.urls import path

app_name = "api"

router = DefaultRouter()

# Accounts
router.register("users", UserViewSet)
router.register("addresses", AddressViewSet)
router.register("producers", ProducerViewSet)
router.register("admins", AdminViewSet)
router.register("customers", CustomerViewSet)

# Admin records
router.register("security-logs", SecurityLogViewSet)
router.register("admin-posts", AdminPostViewSet)
router.register("moderation-logs", ModerationLogViewSet)
router.register("distance-records", DistanceRecordViewSet)

# Community
router.register("recipes", RecipeViewSet)
router.register("recipe-products", RecipeProductViewSet)
router.register("farm-stories", FarmStoryViewSet)
router.register("favourite-recipes", FavouriteRecipeViewSet)

# Notifications
router.register("notifications", NotificationViewSet)
router.register("recall-notices", RecallNoticeViewSet)
router.register("recall-notifications", RecallNotificationViewSet)
router.register("traceability-records", TraceabilityRecordViewSet)

# Orders
router.register("orders", OrderViewSet)
router.register("order-items", OrderItemViewSet)
router.register("producer-order-summaries", ProducerOrderSummaryViewSet)
router.register("producer-order-status-history", ProducerOrderStatusHistoryViewSet)
router.register("recurring-orders", RecurringOrderViewSet)
router.register("recurring-order-items", RecurringOrderItemViewSet)

# Payments
router.register("payments", PaymentViewSet)
router.register("producer-settlements", ProducerSettlementViewSet)
router.register("settlement-line-items", SettlementLineItemViewSet)

# Products
router.register("categories", CategoryViewSet)
router.register("products", ProductViewSet)
router.register("wholesale-prices", WholesalePriceViewSet)
router.register("product-update-history", ProductUpdateHistoryViewSet)
router.register("allergens", AllergenViewSet)
router.register("product-allergens", ProductAllergenViewSet)

# Reviews
router.register("reviews", ReviewViewSet)
router.register("review-responses", ReviewResponseViewSet)

# Carts
router.register("cart", CartViewSet, basename="cart")

#urlpatterns = router.urls



urlpatterns = [
    path("checkout/", CheckoutAPIView.as_view(), name="checkout"),
]

urlpatterns += router.urls