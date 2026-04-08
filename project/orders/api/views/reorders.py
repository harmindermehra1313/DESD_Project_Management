"""
orders/api/views/reorders.py

Purpose:
Expose API endpoints for order history, order detail, and reorder actions.

Responsibilities:
- list authenticated user's order history
- retrieve a single authenticated user's order detail
- preview reorder changes without mutating cart
- execute reorder into cart
- validate and parse query-string filter values
- validate reorder request payloads
- convert missing-order cases into HTTP 404 responses
"""

from __future__ import annotations

from datetime import date

from django.http import Http404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.api.serializers.reorders import (
    OrderDetailSerializer,
    OrderHistorySerializer,
    ReorderResponseSerializer,
    ReorderSelectionRequestSerializer,
)
from orders.selectors import get_order_detail_for_user, get_order_history_for_user
from orders.services.reorder_service import reorder_order


class OrderHistoryPagination(PageNumberPagination):
    """
    Pagination settings for the order history endpoint.
    """

    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


def _parse_date(value: str | None, field_name: str) -> date | None:
    if not value:
        return None

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError({field_name: ["Invalid date format. Use YYYY-MM-DD."]}) from exc


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
    if value is None:
        return None

    if value == "":
        return None

    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError({field_name: [f"A valid {field_name} is required."]}) from exc


def _raise_not_found_if_needed(exc: Exception) -> None:
    model = getattr(exc, "__class__", None)
    if model and model.__name__ == "DoesNotExist":
        raise Http404("Order not found.")
    raise exc


class OrderHistoryApiView(generics.ListAPIView):
    serializer_class = OrderHistorySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = OrderHistoryPagination

    def get_queryset(self):
        params = self.request.query_params

        start_date = _parse_date(params.get("start_date"), "start_date")
        end_date = _parse_date(params.get("end_date"), "end_date")
        producer_id = _parse_int(params.get("producer_id"), "producer_id")
        today = date.today()

        if start_date and start_date > today:
            raise ValidationError({"start_date": ["Start date cannot be in the future."]})

        if end_date and end_date > today:
            raise ValidationError({"end_date": ["End date cannot be in the future."]})

        if start_date and end_date and start_date > end_date:
            raise ValidationError(
                {"date_range": ["Start date must be earlier than or equal to end date."]}
            )

        return get_order_history_for_user(
            user=self.request.user,
            status=params.get("status") or None,
            producer_id=producer_id,
            start_date=start_date,
            end_date=end_date,
            delivery_or_collection=params.get("delivery_or_collection") or None,
        )


class OrderDetailApiView(generics.RetrieveAPIView):
    serializer_class = OrderDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_url_kwarg = "order_id"

    def get_object(self):
        order_id = self.kwargs["order_id"]

        try:
            return get_order_detail_for_user(
                user=self.request.user,
                order_id=order_id,
            )
        except Exception as exc:
            _raise_not_found_if_needed(exc)


class BaseReorderApiView(APIView):
    """
    Shared base class for reorder preview and reorder commit endpoints.

    Subclasses choose whether the service call should mutate the cart by
    setting commit = True or commit = False.
    """

    permission_classes = [permissions.IsAuthenticated]
    commit = False
    request_serializer_class = ReorderSelectionRequestSerializer

    def _get_validated_selections(self, request) -> list[dict] | None:
        serializer = self.request_serializer_class(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data.get("selections")

    def post(self, request, order_id: int, *args, **kwargs):
        selections = self._get_validated_selections(request)

        try:
            result = reorder_order(
                user=request.user,
                order_id=order_id,
                commit=self.commit,
                selections=selections,
            )
        except ValidationError:
            raise
        except Exception as exc:
            _raise_not_found_if_needed(exc)

        serializer = ReorderResponseSerializer(result)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ReorderPreviewApiView(BaseReorderApiView):
    """
    Preview reorder changes without adding anything to the cart.

    This endpoint also accepts an optional selections payload so the
    frontend can recalculate preview pricing and quantities for the user's
    current choices.
    """

    commit = False


class ReorderOrderApiView(BaseReorderApiView):
    """
    Execute reorder and add selected items to the cart.
    """

    commit = True
