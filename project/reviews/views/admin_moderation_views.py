from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from reviews.models import Review, ReviewProducerResponse
from accounts.models import Admin


def _is_platform_admin(user):
    if not user.is_authenticated:
        return False

    role = str(getattr(user, "role", "") or "").upper()

    return bool(
        getattr(user, "is_staff", False)
        or getattr(user, "is_superuser", False)
        or role == "ADMIN"
    )


def _status_value(model_class, name, fallback=None):
    status_class = getattr(model_class, "Status", None)

    if status_class is None:
        return fallback

    return getattr(status_class, name, fallback)


def _build_admin_note(*, existing_notes, action_label, admin_user, admin_note):
    """
    Preserve original automatic moderation notes,
    but keep only the latest admin moderation decision.
    """
    timestamp = timezone.localtime().strftime("%d %b %Y, %H:%M")

    admin_label = (
        getattr(admin_user, "email", None)
        or getattr(admin_user, "username", None)
        or "Admin"
    )

    new_admin_note = f"[{timestamp}] Admin moderation: {action_label} by {admin_label}."

    cleaned_admin_note = (admin_note or "").strip()
    if cleaned_admin_note:
        new_admin_note = f"{new_admin_note}\nAdmin note: {cleaned_admin_note}"

    existing_notes = (existing_notes or "").strip()

    preserved_blocks = []

    if existing_notes:
        for block in existing_notes.split("\n\n"):
            cleaned_block = block.strip()

            if not cleaned_block:
                continue

            if "Admin moderation:" not in cleaned_block:
                preserved_blocks.append(cleaned_block)

    preserved_blocks.append(new_admin_note)

    return "\n\n".join(preserved_blocks)


def _status_already_applied(*, instance, target_status, message, request):
    if str(instance.status) == str(target_status):
        messages.info(request, message)
        return True

    return False


def _get_admin_profile_for_user(user):
    """
    Review.moderated_by_admin expects accounts.Admin, not accounts.User.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return None

    admin_profile = getattr(user, "admin_profile", None)

    if isinstance(admin_profile, Admin):
        return admin_profile

    return Admin.objects.filter(user_id=user.pk).first()


def _set_moderation_admin(instance, admin_user):
    if not hasattr(instance, "moderated_by_admin"):
        return

    admin_profile = _get_admin_profile_for_user(admin_user)

    if admin_profile is not None:
        instance.moderated_by_admin = admin_profile


def _save_moderated_instance(instance):
    instance.full_clean()
    instance.save()
    return instance


def _redirect_back(request):
    next_url = request.POST.get("next", "")

    if next_url.startswith("/"):
        return redirect(next_url)

    return redirect("reviews:admin_review_moderation")


@login_required
@user_passes_test(_is_platform_admin)
def admin_review_moderation(request):
    search = (request.GET.get("q") or "").strip()
    review_status = (request.GET.get("review_status") or "flagged").strip()
    response_status = (request.GET.get("response_status") or "flagged").strip()

    review_status_map = {
        "flagged": Review.Status.FLAGGED,
        "published": Review.Status.PUBLISHED,
        "removed": Review.Status.REMOVED,
        "all": None,
    }

    response_status_map = {
        "flagged": ReviewProducerResponse.Status.FLAGGED,
        "published": ReviewProducerResponse.Status.PUBLISHED,
        "all": None,
    }

    response_removed_status = _status_value(
        ReviewProducerResponse,
        "REMOVED",
        None,
    )

    if response_removed_status is not None:
        response_status_map["removed"] = response_removed_status

    selected_review_status = review_status_map.get(
        review_status,
        Review.Status.FLAGGED,
    )

    selected_response_status = response_status_map.get(
        response_status,
        ReviewProducerResponse.Status.FLAGGED,
    )

    reviews = Review.objects.select_related(
        "customer",
        "customer__user",
        "product",
        "order",
        "order_item",
    )

    producer_responses = ReviewProducerResponse.objects.select_related(
        "review",
        "review__customer",
        "review__customer__user",
        "review__product",
        "responder",
    )

    if review_status == "flagged":
        reviews = reviews.order_by("-created_at", "-id")
    else:
        reviews = reviews.annotate(
            moderation_activity_at=Coalesce("moderated_at", "created_at")
        ).order_by("-moderation_activity_at", "-id")

    if response_status == "flagged":
        producer_responses = producer_responses.order_by("-created_at", "-id")
    else:
        producer_responses = producer_responses.annotate(
            moderation_activity_at=Coalesce("moderated_at", "created_at")
        ).order_by("-moderation_activity_at", "-id")

    if selected_review_status is not None:
        reviews = reviews.filter(status=selected_review_status)

    if selected_response_status is not None:
        producer_responses = producer_responses.filter(status=selected_response_status)

    if search:
        review_query = (
            Q(title__icontains=search)
            | Q(text__icontains=search)
            | Q(product__name__icontains=search)
            | Q(customer__user__email__icontains=search)
        )

        response_query = (
            Q(text__icontains=search)
            | Q(review__title__icontains=search)
            | Q(review__text__icontains=search)
            | Q(review__product__name__icontains=search)
            | Q(review__customer__user__email__icontains=search)
        )

        if search.isdigit():
            review_query |= Q(order_id=int(search))
            response_query |= Q(review__order_id=int(search))

        reviews = reviews.filter(review_query)
        producer_responses = producer_responses.filter(response_query)

    review_paginator = Paginator(reviews, 10)
    response_paginator = Paginator(producer_responses, 10)

    review_page = review_paginator.get_page(request.GET.get("review_page"))
    response_page = response_paginator.get_page(request.GET.get("response_page"))

    review_counts = {
        "flagged": Review.objects.filter(status=Review.Status.FLAGGED).count(),
        "published": Review.objects.filter(status=Review.Status.PUBLISHED).count(),
        "removed": Review.objects.filter(status=Review.Status.REMOVED).count(),
        "all": Review.objects.count(),
    }

    response_counts = {
        "flagged": ReviewProducerResponse.objects.filter(
            status=ReviewProducerResponse.Status.FLAGGED
        ).count(),
        "published": ReviewProducerResponse.objects.filter(
            status=ReviewProducerResponse.Status.PUBLISHED
        ).count(),
        "all": ReviewProducerResponse.objects.count(),
    }

    if response_removed_status is not None:
        response_counts["removed"] = ReviewProducerResponse.objects.filter(
            status=response_removed_status
        ).count()

    return render(
        request,
        "reviews/admin/review_moderation.html",
        {
            "search": search,
            "review_status": review_status,
            "response_status": response_status,
            "review_page": review_page,
            "response_page": response_page,
            "review_counts": review_counts,
            "response_counts": response_counts,
            "response_has_removed_status": response_removed_status is not None,
            "current_url": request.get_full_path(),
            "review_status_values": {
                "flagged": Review.Status.FLAGGED,
                "published": Review.Status.PUBLISHED,
                "removed": Review.Status.REMOVED,
            },
            "response_status_values": {
                "flagged": ReviewProducerResponse.Status.FLAGGED,
                "published": ReviewProducerResponse.Status.PUBLISHED,
                "removed": response_removed_status,
            },
        },
    )


@login_required
@user_passes_test(_is_platform_admin)
@require_POST
def admin_moderate_review(request, review_id):
    review = get_object_or_404(Review, id=review_id)

    action = (request.POST.get("action") or "").strip()
    admin_note = request.POST.get("admin_note", "")

    if action == "publish":
        target_status = Review.Status.PUBLISHED
        action_label = "Customer review approved and published"
        success_message = "Customer review approved and published."
        already_message = "Customer review is already published. No change made."

    elif action == "remove":
        target_status = Review.Status.REMOVED
        action_label = "Customer review removed after admin moderation"
        success_message = "Customer review removed."
        already_message = "Customer review is already removed. No change made."

    elif action == "flag":
        target_status = Review.Status.FLAGGED
        action_label = "Customer review kept flagged for moderation"
        success_message = "Customer review kept flagged."
        already_message = "Customer review is already flagged. No change made."

    else:
        messages.error(request, "Invalid moderation action.")
        return _redirect_back(request)

    if _status_already_applied(
        instance=review,
        target_status=target_status,
        message=already_message,
        request=request,
    ):
        return _redirect_back(request)

    review.status = target_status
    review.moderated_at = timezone.now()
    _set_moderation_admin(review, request.user)

    review.moderation_notes = _build_admin_note(
        existing_notes=review.moderation_notes,
        action_label=action_label,
        admin_user=request.user,
        admin_note=admin_note,
    )

    try:
        _save_moderated_instance(review)
    except ValidationError as exc:
        messages.error(request, f"Review could not be moderated: {exc}")
        return _redirect_back(request)

    messages.success(request, success_message)
    return _redirect_back(request)


@login_required
@user_passes_test(_is_platform_admin)
@require_POST
def admin_moderate_producer_response(request, response_id):
    response = get_object_or_404(ReviewProducerResponse, id=response_id)

    action = (request.POST.get("action") or "").strip()
    admin_note = request.POST.get("admin_note", "")

    if action == "publish":
        target_status = ReviewProducerResponse.Status.PUBLISHED
        action_label = "Producer response approved and published"
        success_message = "Producer response approved and published."
        already_message = "Producer response is already published. No change made."

    elif action == "remove":
        removed_status = _status_value(
            ReviewProducerResponse,
            "REMOVED",
            None,
        )

        if removed_status is not None:
            target_status = removed_status
            action_label = "Producer response removed after admin moderation"
            success_message = "Producer response removed."
            already_message = "Producer response is already removed. No change made."
        else:
            target_status = ReviewProducerResponse.Status.FLAGGED
            action_label = (
                "Producer response rejected by admin but kept flagged "
                "because no removed status exists"
            )
            success_message = (
                "Producer response kept flagged. Add a removed status later "
                "if producer responses need a separate removed state."
            )
            already_message = "Producer response is already flagged. No change made."

    elif action == "flag":
        target_status = ReviewProducerResponse.Status.FLAGGED
        action_label = "Producer response kept flagged for moderation"
        success_message = "Producer response kept flagged."
        already_message = "Producer response is already flagged. No change made."

    else:
        messages.error(request, "Invalid moderation action.")
        return _redirect_back(request)

    if _status_already_applied(
        instance=response,
        target_status=target_status,
        message=already_message,
        request=request,
    ):
        return _redirect_back(request)

    response.status = target_status
    response.moderated_at = timezone.now()
    _set_moderation_admin(response, request.user)

    response.moderation_notes = _build_admin_note(
        existing_notes=response.moderation_notes,
        action_label=action_label,
        admin_user=request.user,
        admin_note=admin_note,
    )

    try:
        _save_moderated_instance(response)
    except ValidationError as exc:
        messages.error(request, f"Producer response could not be moderated: {exc}")
        return _redirect_back(request)

    messages.success(request, success_message)
    return _redirect_back(request)
