from django.views.generic import TemplateView

class CartPageView(TemplateView):
    template_name = "carts/cart_page.html"