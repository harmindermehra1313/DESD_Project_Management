from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied
from ..models import Inventory, InventoryUpdateHistory
from ..serializers.reductions_serializers import SurplusCreateSerializer, SurplusUpdateSerializer, SurplusOutputSerializer
from rest_framework.response import Response
import logging
logger = logging.getLogger(__name__)

class SurplusListAPI(generics.ListAPIView):
    serializer_class = SurplusOutputSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Inventory.objects.filter(
            product__producer=self.request.user.producer_profile,
            surplus_status=Inventory.SurplusStatus.SURPLUS_ACTIVE
        )


class SurplusCreateAPI(generics.UpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Inventory.objects.all()
    serializer_class = SurplusOutputSerializer  # RESPONSE serializer

    def get_input_serializer(self, *args, **kwargs):
        kwargs.setdefault("context", self.get_serializer_context())
        return SurplusCreateSerializer(*args, **kwargs)

    def update(self, request, *args, **kwargs):
        batch = self.get_object()

        logger.warning(f"[API CREATE RECEIVED] request.data = {request.data}")

        if batch.product.producer != request.user.producer_profile:
            raise PermissionDenied("Not your inventory.")

        # Validate input
        input_serializer = self.get_input_serializer(
            instance=batch,
            data=request.data,
            partial=True
        )
        input_serializer.is_valid(raise_exception=True)

        # Capture old values
        old_discount = batch.surplus_discount_percentage
        old_expiry = batch.surplus_expiry
        old_note = batch.surplus_note
        old_status = batch.surplus_status

        # Save new values
        updated_batch = input_serializer.save(
            surplus_status=Inventory.SurplusStatus.SURPLUS_ACTIVE
        )

        logger.warning(f"[MODEL CREATE SAVE] saving discount = {updated_batch.surplus_discount_percentage}")

        # Log changes
        user = request.user

        if old_discount != updated_batch.surplus_discount_percentage:
            InventoryUpdateHistory.objects.create(
                inventory=batch,
                user=user,
                field_changed="surplus_discount_percentage",
                old_value=str(old_discount),
                new_value=str(updated_batch.surplus_discount_percentage)
            )

        if old_expiry != updated_batch.surplus_expiry:
            InventoryUpdateHistory.objects.create(
                inventory=batch,
                user=user,
                field_changed="surplus_expiry",
                old_value=str(old_expiry),
                new_value=str(updated_batch.surplus_expiry)
            )

        if old_note != updated_batch.surplus_note:
            InventoryUpdateHistory.objects.create(
                inventory=batch,
                user=user,
                field_changed="surplus_note",
                old_value=str(old_note),
                new_value=str(updated_batch.surplus_note)
            )

        if old_status != updated_batch.surplus_status:
            InventoryUpdateHistory.objects.create(
                inventory=batch,
                user=user,
                field_changed="surplus_status",
                old_value=old_status,
                new_value=updated_batch.surplus_status
            )

        # Log reduction started event
        if old_status == Inventory.SurplusStatus.NONE:
            InventoryUpdateHistory.objects.create(
                inventory=batch,
                user=user,
                event_type="reduction_started",
                ended_reason=None
            )

        # Return OUTPUT serializer
        output_serializer = self.get_serializer(updated_batch)
        return Response(output_serializer.data)


class SurplusUpdateAPI(generics.UpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Inventory.objects.all()
    serializer_class = SurplusOutputSerializer  # RESPONSE serializer

    def get_input_serializer(self, *args, **kwargs):
        kwargs.setdefault("context", self.get_serializer_context())
        return SurplusUpdateSerializer(*args, **kwargs)

    def update(self, request, *args, **kwargs):
        batch = self.get_object()

        logger.warning(f"[API UPDATE RECEIVED] request.data = {request.data}")

        if batch.product.producer != request.user.producer_profile:
            raise PermissionDenied("Not your inventory.")

        # Validate input
        input_serializer = self.get_input_serializer(
            instance=batch,
            data=request.data,
            partial=True
        )
        input_serializer.is_valid(raise_exception=True)

        # Capture old values
        old_discount = batch.surplus_discount_percentage
        old_expiry = batch.surplus_expiry
        old_note = batch.surplus_note

        # Save
        updated_batch = input_serializer.save()

        logger.warning(f"[MODEL UPDATE SAVE] saving discount = {updated_batch.surplus_discount_percentage}")

        # Log changes
        user = request.user

        if old_discount != updated_batch.surplus_discount_percentage:
            InventoryUpdateHistory.objects.create(
                inventory=batch,
                user=user,
                field_changed="surplus_discount_percentage",
                old_value=str(old_discount),
                new_value=str(updated_batch.surplus_discount_percentage)
            )

        if old_expiry != updated_batch.surplus_expiry:
            InventoryUpdateHistory.objects.create(
                inventory=batch,
                user=user,
                field_changed="surplus_expiry",
                old_value=str(old_expiry),
                new_value=str(updated_batch.surplus_expiry)
            )

        if old_note != updated_batch.surplus_note:
            InventoryUpdateHistory.objects.create(
                inventory=batch,
                user=user,
                field_changed="surplus_note",
                old_value=str(old_note),
                new_value=str(updated_batch.surplus_note)
            )

        # Return OUTPUT serializer
        output_serializer = self.get_serializer(updated_batch)
        return Response(output_serializer.data)


class SurplusCancelAPI(generics.UpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Inventory.objects.all()
    serializer_class = SurplusOutputSerializer  # RESPONSE serializer

    def get_input_serializer(self, *args, **kwargs):
        kwargs.setdefault("context", self.get_serializer_context())
        return SurplusUpdateSerializer(*args, **kwargs)

    def update(self, request, *args, **kwargs):
        batch = self.get_object()

        if batch.product.producer != request.user.producer_profile:
            raise PermissionDenied("Not your inventory.")

        # Validate input (even though cancel sends {})
        input_serializer = self.get_input_serializer(
            instance=batch,
            data=request.data,
            partial=True
        )
        input_serializer.is_valid(raise_exception=True)

        # Capture old values
        old_discount = batch.surplus_discount_percentage
        old_expiry = batch.surplus_expiry
        old_note = batch.surplus_note
        old_status = batch.surplus_status

        # Save cancel changes
        updated_batch = input_serializer.save(
            surplus_status=Inventory.SurplusStatus.NONE,
            surplus_discount_percentage=None,
            surplus_expiry=None,
            surplus_note=None
        )

        # Log changes
        user = request.user

        if old_discount is not None:
            InventoryUpdateHistory.objects.create(
                inventory=batch,
                user=user,
                field_changed="surplus_discount_percentage",
                old_value=str(old_discount),
                new_value="None"
            )

        if old_expiry is not None:
            InventoryUpdateHistory.objects.create(
                inventory=batch,
                user=user,
                field_changed="surplus_expiry",
                old_value=str(old_expiry),
                new_value="None"
            )

        if old_note is not None:
            InventoryUpdateHistory.objects.create(
                inventory=batch,
                user=user,
                field_changed="surplus_note",
                old_value=str(old_note),
                new_value="None"
            )

        if old_status != Inventory.SurplusStatus.NONE:
            InventoryUpdateHistory.objects.create(
                inventory=batch,
                user=user,
                field_changed="surplus_status",
                old_value=old_status,
                new_value=Inventory.SurplusStatus.NONE
            )

        InventoryUpdateHistory.objects.create(
            inventory=batch,
            user=user,
            event_type="reduction_ended",
            ended_reason="cancelled",
            snapshot_discount=old_discount,
            snapshot_expiry=old_expiry,
            snapshot_note=old_note
        )

        # Return OUTPUT serializer
        output_serializer = self.get_serializer(updated_batch)
        return Response(output_serializer.data)