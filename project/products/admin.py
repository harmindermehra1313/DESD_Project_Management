from django.contrib import admin
from .models import Product, Category, WholesalePrice, Allergen, ProductAllergen, ProductType

# admin.site.register(Product)
admin.site.register(Category)
admin.site.register(WholesalePrice)
admin.site.register(Allergen)
admin.site.register(ProductAllergen)

@admin.register(ProductType)
class ProductTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "category")
    search_fields = ("name", "category__name")
    list_filter = ("category",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "producer", "category", "product_type", "status")
    list_filter = ("category", "product_type", "status", "availability_status")
    search_fields = ("name", "producer__farm_name")