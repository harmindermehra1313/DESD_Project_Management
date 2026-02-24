from django.shortcuts import render, redirect, get_object_or_404
from django.apps import apps

Product = apps.get_model('products', 'Product')
Order = apps.get_model('orders', 'Order')

def fake_add_to_cart(request):
    # TBC Temporary cart structure with multiple items
    # request.session["cart"] = {
    #     "items":[
    #     {"product_id": 1, "quantity": 1},
    #     {"product_id": 2, "quantity": 2},
    #     ]
    # }
    products = Product.objects.all()[:2]

    request.session["cart"] = {
        "items": [
            {"product_id": products[0].id, "quantity": 2},
            {"product_id": products[1].id, "quantity": 1},
        ]
    }

    return redirect("orders:checkout")

def checkout(request):
    cart = request.session.get("cart", {})
    items = cart.get("items", [])

    enriched_items = []
    total = 0

    for entry in items:
        product = Product.objects.get(id=entry["product_id"])
        quantity = entry["quantity"]
        subtotal = product.price * quantity

        enriched_items.append({
            "product": product,
            "quantity": quantity,
            "subtotal": subtotal,
        })

        total += subtotal

    context = {
        "cart": {
            "items": enriched_items,
            "total": total,
        }
    }

    return render(request, "orders/checkout.html", context)

def order_success(request, reference):
    order = Order.objects.get(unique_reference=reference)

    return render(request, "orders/order_confirmed.html", {
        "order": order
    })