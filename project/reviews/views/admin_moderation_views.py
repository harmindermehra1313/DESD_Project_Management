from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.models import Admin
from reviews.models import Review, ReviewProducerResponse
from notifications.services.notifications import NotificationService

ADMIN_NOTE_MAX_LENGTH = 500
ACTIONS_REQUIRING_NOTE = {"remove", "flag"}
DEFAULT_STATUS_FILTER = "flagged"
ITEMS_PER_PAGE = 10


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


def _normalise_status_filter(value, status_map):
    value = (value or DEFAULT_STATUS_FILTER).strip().lower()

    if value not in status_map:
        return DEFAULT_STATUS_FILTER

    return value


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


def _validate_admin_note_for_action(*, request, action, admin_note, content_label):
    cleaned_note = (admin_note or "").strip()

    if len(cleaned_note) > ADMIN_NOTE_MAX_LENGTH:
        messages.error(
            request,
            f"Admin note must be {ADMIN_NOTE_MAX_LENGTH} characters or fewer.",
        )
        return False, cleaned_note

    if action in ACTIONS_REQUIRING_NOTE and not cleaned_note:
        messages.error(
            request,
            f"Admin note is required when removing or rejecting {content_label}.",
        )
        return False, cleaned_note

    return True, cleaned_note


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

    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)

    return redirect(reverse("reviews:admin_review_moderation"))


def _build_review_status_map():
    return {
        "flagged": Review.Status.FLAGGED,
        "published": Review.Status.PUBLISHED,
        "removed": Review.Status.REMOVED,
        "all": None,
    }


def _build_response_status_map():
    status_map = {
        "flagged": ReviewProducerResponse.Status.FLAGGED,
        "published": ReviewProducerResponse.Status.PUBLISHED,
        "all": None,
    }

    removed_status = _status_value(
        ReviewProducerResponse,
        "REMOVED",
        None,
    )

    if removed_status is not None:
        status_map["removed"] = removed_status

    return status_map, removed_status


def _apply_search_filters(*, reviews, producer_responses, search):
    if not search:
        return reviews, producer_responses

    review_query = (
        Q(title__icontains=search)
        | Q(text__icontains=search)
        | Q(product__name__icontains=search)
        | Q(customer__user__email__icontains=search)
        | Q(customer__user__name__icontains=search)
    )

    response_query = (
        Q(text__icontains=search)
        | Q(review__title__icontains=search)
        | Q(review__text__icontains=search)
        | Q(review__product__name__icontains=search)
        | Q(review__customer__user__email__icontains=search)
        | Q(review__customer__user__name__icontains=search)
        | Q(responder__email__icontains=search)
        | Q(responder__name__icontains=search)
    )

    if search.isdigit():
        search_id = int(search)

        review_query |= (
            Q(id=search_id)
            | Q(order_id=search_id)
            | Q(order_item_id=search_id)
            | Q(product_id=search_id)
        )

        response_query |= (
            Q(id=search_id)
            | Q(review_id=search_id)
            | Q(review__order_id=search_id)
            | Q(review__order_item_id=search_id)
            | Q(review__product_id=search_id)
        )

    return reviews.filter(review_query), producer_responses.filter(response_query)


def _order_reviews_for_filter(queryset, status_filter):
    if status_filter == "flagged":
        return queryset.order_by("-created_at", "-id")

    return queryset.annotate(
        moderation_activity_at=Coalesce("moderated_at", "created_at")
    ).order_by("-moderation_activity_at", "-id")


def _order_responses_for_filter(queryset, status_filter):
    if status_filter == "flagged":
        return queryset.order_by("-created_at", "-id")

    return queryset.annotate(
        moderation_activity_at=Coalesce("moderated_at", "created_at")
    ).order_by("-moderation_activity_at", "-id")


@login_required
@user_passes_test(_is_platform_admin)
def admin_review_moderation(request):
    search = (request.GET.get("q") or "").strip()

    review_status_map = _build_review_status_map()
    response_status_map, response_removed_status = _build_response_status_map()

    review_status = _normalise_status_filter(
        request.GET.get("review_status"),
        review_status_map,
    )
    response_status = _normalise_status_filter(
        request.GET.get("response_status"),
        response_status_map,
    )

    selected_review_status = review_status_map[review_status]
    selected_response_status = response_status_map[response_status]

    reviews = Review.objects.select_related(
        "customer",
        "customer__user",
        "product",
        "order",
        "order_item",
        "moderated_by_admin",
        "moderated_by_admin__user",
    )

    producer_responses = ReviewProducerResponse.objects.select_related(
        "review",
        "review__customer",
        "review__customer__user",
        "review__product",
        "review__order",
        "review__order_item",
        "responder",
    )

    if selected_review_status is not None:
        reviews = reviews.filter(status=selected_review_status)

    if selected_response_status is not None:
        producer_responses = producer_responses.filter(status=selected_response_status)

    reviews, producer_responses = _apply_search_filters(
        reviews=reviews,
        producer_responses=producer_responses,
        search=search,
    )

    reviews = _order_reviews_for_filter(reviews, review_status)
    producer_responses = _order_responses_for_filter(
        producer_responses,
        response_status,
    )

    review_paginator = Paginator(reviews, ITEMS_PER_PAGE)
    response_paginator = Paginator(producer_responses, ITEMS_PER_PAGE)

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
            "admin_note_max_length": ADMIN_NOTE_MAX_LENGTH,
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
    old_status = review.status

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

    is_note_valid, admin_note = _validate_admin_note_for_action(
        request=request,
        action=action,
        admin_note=admin_note,
        content_label="this customer review",
    )

    if not is_note_valid:
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
    if target_status == Review.Status.PUBLISHED:
        if old_status == Review.Status.FLAGGED:
            NotificationService.notify_review_flag_rejected_and_published(review)
        else:
            NotificationService.notify_review_published_after_submission(review)

    elif target_status == Review.Status.REMOVED:
        NotificationService.notify_review_removed_after_moderation(review)

    elif target_status == Review.Status.FLAGGED:
        NotificationService.notify_review_kept_flagged_after_moderation(review)

    if target_status != Review.Status.FLAGGED:
        NotificationService.resolve_admin_review_flagged_notifications(review)

    messages.success(request, success_message)
    return _redirect_back(request)


@login_required
@user_passes_test(_is_platform_admin)
@require_POST
def admin_moderate_producer_response(request, response_id):
    response = get_object_or_404(ReviewProducerResponse, id=response_id)
    old_status = response.status

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

    is_note_valid, admin_note = _validate_admin_note_for_action(
        request=request,
        action=action,
        admin_note=admin_note,
        content_label="this producer response",
    )

    if not is_note_valid:
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
    if target_status == ReviewProducerResponse.Status.PUBLISHED:
        if old_status == ReviewProducerResponse.Status.FLAGGED:
            NotificationService.notify_producer_response_approved_after_moderation(
                response
            )
        else:
            NotificationService.notify_producer_response_published_after_submission(
                response
            )

    elif target_status == ReviewProducerResponse.Status.FLAGGED:
        NotificationService.notify_producer_response_kept_flagged_after_moderation(
            response
        )

    else:
        NotificationService.notify_producer_response_removed_after_moderation(response)

    if target_status != ReviewProducerResponse.Status.FLAGGED:
        NotificationService.resolve_admin_producer_response_flagged_notifications(
            response
        )

    messages.success(request, success_message)
    return _redirect_back(request)
