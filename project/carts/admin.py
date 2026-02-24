from django.contrib import admin
from .models import Cart, CartItem

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "guest_token", "status", "updated_at", "expires_at")
    list_filter = ("status",)
    search_fields = ("user__email", "guest_token")

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "cart", "product", "quantity", "updated_at")
    search_fields = ("cart__id", "product__name")
