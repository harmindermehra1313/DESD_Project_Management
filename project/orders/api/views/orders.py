"""
orders/api/views/orders.py

Purpose:
Expose API endpoints for order history, order detail, and reorder actions.

This module is the HTTP entry point for the order history feature. It is
responsible for request parsing, authentication, response serialisation,
and translation of domain exceptions into HTTP-level behaviour.

Responsibilities:
- list authenticated user's order history
- retrieve a single authenticated user's order detail
- trigger reorder of a completed order
- validate and parse query-string filter values
- convert missing-order cases into HTTP 404 responses

Layering rules:
- views should remain thin
- ORM query logic belongs in selectors
- reorder business logic belongs in services
- serializers define response structure
"""

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
    """
    Pagination settings for the order history endpoint.

    Defaults:
    - page size: 10
    - client override allowed through page_size query parameter
    - maximum page size: 100
    """

    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


def _parse_date(value: str | None) -> date | None:
    """
    Parse an ISO date string from query parameters.

    Accepted format:
    - YYYY-MM-DD

    Args:
        value: Raw string value from the query string.

    Returns:
        date | None:
            Parsed date object, or None when the value is empty.

    Raises:
        ValidationError:
            Raised when the value is present but not a valid ISO date.
    """
    if not value:
        return None

    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValidationError({"date": ["Invalid date format. Use YYYY-MM-DD."]})


def _parse_bool(value: str | None) -> bool | None:
    """
    Parse a boolean-like query parameter.

    Accepted true values:
    - true
    - 1
    - yes

    Accepted false values:
    - false
    - 0
    - no

    Args:
        value: Raw string value from the query string.

    Returns:
        bool | None:
            Parsed boolean value, or None when the value is empty.

    Raises:
        ValidationError:
            Raised when the value is present but not recognised as boolean.
    """
    if value is None or value == "":
        return None

    normalized = value.strip().lower()

    if normalized in {"true", "1", "yes"}:
        return True

    if normalized in {"false", "0", "no"}:
        return False

    raise ValidationError({"recurring_only": ["Invalid boolean value."]})


def _parse_int(value: str | None, field_name: str) -> int | None:
    """
    Parse an integer query parameter.

    Args:
        value: Raw string value from the query string.
        field_name: Field name used in the validation error response.

    Returns:
        int | None:
            Parsed integer value, or None when the value is empty.

    Raises:
        ValidationError:
            Raised when the value is present but not a valid integer.
    """
    if value is None or value == "":
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError({field_name: ["A valid integer is required."]})


class OrderHistoryApiView(generics.ListAPIView):
    """
    Return a paginated list of the authenticated user's orders.

    Supported query parameters:
    - status
    - producer_id
    - start_date
    - end_date
    - delivery_or_collection
    - recurring_only

    Query parsing is handled inside get_queryset() so invalid query values
    fail early with API-friendly validation errors.
    """

    serializer_class = OrderHistorySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = OrderHistoryPagination

    def get_queryset(self):
        """
        Build the filtered order history queryset for the authenticated user.

        Returns:
            QuerySet[Order]:
                User-scoped and optimised queryset ready for pagination.
        """
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
    """
    Return one order belonging to the authenticated user.

    The selector enforces ownership at query level. Missing or unauthorised
    orders are converted into HTTP 404 so object existence is not leaked.
    """

    serializer_class = OrderDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_url_kwarg = "order_id"

    def get_object(self):
        """
        Fetch one user-scoped order instance for detail serialisation.

        Returns:
            Order:
                Fully loaded order instance.

        Raises:
            Http404:
                Raised when the order does not exist for the authenticated user.
        """
        order_id = self.kwargs["order_id"]

        try:
            return get_order_detail_for_user(user=self.request.user, order_id=order_id)
        except Exception as exc:
            model = getattr(exc, "__class__", None)
            if model and model.__name__ == "DoesNotExist":
                raise Http404("Order not found.")
            raise


class ReorderOrderApiView(APIView):
    """
    Rebuild the current user's cart from a previous completed order.

    The response always returns a structured payload describing:
    - items added successfully
    - items rejected
    - quantity reductions
    - price differences
    - overall outcome message
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_id: int, *args, **kwargs):
        """
        Execute the reorder flow for the specified order.

        Args:
            request:
                DRF request object containing the authenticated user.
            order_id:
                Internal primary key of the source order.

        Returns:
            Response:
                HTTP 200 response containing the validated reorder result.

        Raises:
            Http404:
                Raised when the source order does not exist for the user.
            ValidationError:
                Raised when the order exists but is not eligible for reorder.
        """
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