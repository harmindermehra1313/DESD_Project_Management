from django.contrib import admin
from .models import Product, Category, WholesalePrice, Allergen, ProductAllergen

admin.site.register(Product)
admin.site.register(Category)
admin.site.register(WholesalePrice)
admin.site.register(Allergen)
admin.site.register(ProductAllergen)