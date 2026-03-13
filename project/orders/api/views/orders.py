from __future__ import annotations

from datetime import date

from django.http import Http404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.api.serializers.orders import (
    OrderDetailSerializer,
    OrderHistorySerializer,
    ReorderResponseSerializer,
)
from orders.selectors import get_order_detail_for_user, get_order_history_for_user
from orders.services.reorder_service import reorder_order


class OrderHistoryPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None

    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValidationError({"date": ["Invalid date format. Use YYYY-MM-DD."]})


def _parse_bool(value: str | None) -> bool | None:
    if value is None or value == "":
        return None

    normalized = value.strip().lower()

    if normalized in {"true", "1", "yes"}:
        return True

    if normalized in {"false", "0", "no"}:
        return False

    raise ValidationError({"recurring_only": ["Invalid boolean value."]})


def _parse_int(value: str | None, field_name: str) -> int | None:
    if value is None or value == "":
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError({field_name: ["A valid integer is required."]})


class OrderHistoryApiView(generics.ListAPIView):
    serializer_class = OrderHistorySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = OrderHistoryPagination

    def get_queryset(self):
        params = self.request.query_params

        recurring_only = _parse_bool(params.get("recurring_only"))
        start_date = _parse_date(params.get("start_date"))
        end_date = _parse_date(params.get("end_date"))
        producer_id = _parse_int(params.get("producer_id"), "producer_id")

        return get_order_history_for_user(
            user=self.request.user,
            status=params.get("status") or None,
            producer_id=producer_id,
            start_date=start_date,
            end_date=end_date,
            delivery_or_collection=params.get("delivery_or_collection") or None,
            recurring_only=recurring_only,
        )


class OrderDetailApiView(generics.RetrieveAPIView):
    serializer_class = OrderDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_url_kwarg = "order_id"

    def get_object(self):
        order_id = self.kwargs["order_id"]

        try:
            return get_order_detail_for_user(user=self.request.user, order_id=order_id)
        except Exception as exc:
            model = getattr(exc, "__class__", None)
            if model and model.__name__ == "DoesNotExist":
                raise Http404("Order not found.")
            raise


class ReorderOrderApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_id: int, *args, **kwargs):
        try:
            result = reorder_order(user=request.user, order_id=order_id)
        except Exception as exc:
            model = getattr(exc, "__class__", None)
            if model and model.__name__ == "DoesNotExist":
                raise Http404("Order not found.")
            if isinstance(exc, ValidationError):
                raise exc
            raise

        serializer = ReorderResponseSerializer(result)
        return Response(serializer.data, status=status.HTTP_200_OK)