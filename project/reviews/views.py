from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import TemplateView

from reviews.selectors import get_reviewable_order_item_for_user


class ReviewCreateView(LoginRequiredMixin, TemplateView):
    template_name = "reviews/review_add.html"
    login_url = reverse_lazy("login")

    reviewable_order_item = None

    def _parse_int(self, value: str | None, field_name: str) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise Http404(f"Invalid {field_name}.") from exc

    def _get_next_url(self) -> str:
        candidate = self.request.GET.get("next")
        if candidate and url_has_allowed_host_and_scheme(
            url=candidate,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            return candidate
        return "/orders/history/"

    def dispatch(self, request, *args, **kwargs):
        order_item_id = self._parse_int(request.GET.get("order_item_id"), "order_item_id")
        order_id = self._parse_int(request.GET.get("order_id"), "order_id")
        product_id = self._parse_int(request.GET.get("product_id"), "product_id")

        if order_item_id is None:
            raise Http404("Order item not provided.")

        try:
            self.reviewable_order_item = get_reviewable_order_item_for_user(
                user_id=request.user.id,
                order_item_id=order_item_id,
                order_id=order_id,
                product_id=product_id,
            )
        except PermissionDenied:
            raise
        except Exception as exc:
            raise Http404("Reviewable item not found.") from exc

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "order_item": self.reviewable_order_item,
                "order": self.reviewable_order_item.order,
                "product": self.reviewable_order_item.product,
                "next_url": self._get_next_url(),
                "popup_requested": self.request.GET.get("popup") == "1",
            }
        )
        return context