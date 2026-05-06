// orders/static/orders/order_history_messages.js
(function () {
  function pluralize(count, singular, plural) {
    return `${count} ${count === 1 ? singular : plural}`;
  }

  function formatQuantity(value) {
    const number = Number(value);

    if (!Number.isFinite(number)) {
      return value ?? "0";
    }

    return Number.isInteger(number) ? String(number) : String(number);
  }

  window.OrderHistoryMessages = {
    dash: "-",
    notAvailable: "Not available",
    unavailable: "Unavailable",
    loadFailed: "We couldn't load your order history right now.",
    detailLoadFailed: "We couldn't load those order details right now.",
    previewFailed: "We couldn't open the reorder planner right now.",
    reorderFailed: "We couldn't add the selected items to your cart.",
    previewTitle: "Review your items",
    successTitle: "Added to cart",
    confirmButton: "Add Selected Items to Cart",
    confirmButtonDisabled: "Add Selected Items to Cart",
    submittingButton: "Adding to Cart...",
    reorderNotAvailable: "This order cannot be reordered.",
    reorderButton: "Reorder",
    receiptButton: "See Receipt",
    viewDetailsButton: "View Details",
    closeButton: "Close",
    cancelButton: "Cancel",
    goToCartButton: "Go to Cart",
    reorderAllowedTooltip: "Preview reorder changes",
    reorderBlockedTooltip:
      "Reorder is not available for pending or cancelled orders",
   receiptBlockedTooltip: "Receipt is not available for cancelled orders",
    zeroOrders: "0 orders",
    orderNumberLabel: "Order Number",
    orderDateLabel: "Order Date",
    statusLabel: "Status",
    paymentLabel: "Payment",
    itemsHeading: "Items",
    productLabel: "Product",
    producerLabel: "Producer",
    quantityLabel: "Quantity",
    unitPriceLabel: "Unit Price",
    fulfilmentHeading: "Delivery / Collection Details",
    fulfilmentUnavailable: "Fulfilment information is not available.",
    dateLabel: "Date",
    timeSlotLabel: "Time slot",
    producerDetailsHeading: "Producer Details",
    subtotalLabel: "Subtotal",
    fulfilmentTypeLabel: "Fulfilment type",
    vatLabel: "VAT",
    instructionsLabel: "Instructions",
    totalPaidLabel: "Total Paid",
    addressUnavailable: "Address not available",
    reviewItemsTitle: "Please review your items",
    reviewItemsBody:
      "Before adding items to the cart, check the products below. You can change quantities, choose alternative items where available, or skip anything you do not want.",
    allAvailableSelectedSummary:
      "All available items have been selected for you.",
    estimatedTotalLabel: "Estimated total",
    regularTotalLabel: "Regular total",
    originalBadge: "Original",
    alternativeProducerBadge: "Alternative producer",
    surplusBadge: "Surplus",
    wholesaleBadge: "Wholesale",
    noAlternativeTitle: "No alternative currently available",
    noAlternativeBody: "This item cannot be reordered right now.",
    availableToAddTitle: "Available to add",
    availableToAddSubtitle:
      "This original item is still available and selected for you.",
    chooseAlternativeTitle: "Please choose an alternative",
    chooseAlternativeSubtitle:
      "This original item is unavailable. Choose an alternative item or skip it.",
    currentlyUnavailableTitle: "Currently unavailable",
    currentlyUnavailableSubtitle: "No alternative item is available right now.",
    availableWithAlternativesSubtitle:
      "This original item is available. Alternative items are also available if you prefer.",
    selectedNowLabel: "Selected now",
    totalLabel: "Total",
    skipItemTitle: "Skip this item",
    skipItemBody: "This product will not be added.",
    noReorderableItemsTitle: "No reorderable items found.",
    noReorderableItemsBody:
      "This order does not currently contain any items that can be reordered.",
    availableItemsSectionTitle: "Available items",
    availableItemsSectionSubtitle:
      "These items are available now and are already selected for you.",
    chooseAlternativeItemsSectionTitle: "Choose alternative items",
    chooseAlternativeItemsSectionSubtitle:
      "Some original items are unavailable. Choose an alternative item or skip them.",
    unavailableItemsSectionTitle: "Currently unavailable",
    unavailableItemsSectionSubtitle:
      "These items do not have any alternatives right now.",
    loadingPlannerBody:
      "Checking item availability and finding alternatives...",
    addedBadgeLabel: "added",
    unavailableBadgeLabel: "unavailable",
    quantityUpdatedBadgeLabel: "quantity updated",
    trendingBadge: "Trending",
    newBadge: "New",
    priceChangedBadgeLabel: "price changed",
    addedToCartSectionTitle: "Added to cart",
    unavailableItemsResultTitle: "Unavailable items",
    quantityUpdatesSectionTitle: "Quantity updates",
    priceUpdatesSectionTitle: "Price updates",
    requestedLabel: "Requested",
    addedLabel: "Added",
    requestedReasonLabel: "Reason",
    quantityAddedLabel: "Quantity added",
    selectedAddedBody: "Your selected items were added to the cart.",
    noItemsAddedBody: "No items were added to the cart.",
    resultUpdatesBody:
      "A few updates were made while processing your reorder. Review the details below.",
    resultSuccessBody: "Everything selected was added successfully.",
    currentUnitPriceLabel: "Current unit price",
    basePriceLabel: "Base price",
    lineTotalLabel: "Line total",
    wasLabel: "Was",
    availableNowLabel: "Available now",
    notSpecified: "Not specified",
    skipLabel: "Skip",
    priceChangedPrefix: "Price changed from",
    producerChangedPrefix: "Producer change",
    quantityAdjustmentPrefix: "Requested",
    quantityAdjustmentMiddle: "available now",
    wholesaleActive: "Wholesale active.",
    surplusBetterPrice:
      "Surplus stock exists, but wholesale pricing is currently the better price.",
    surplusApplied: "Surplus discount is applied to this item.",

    productFallback: "this item",
    cartTitle: "Cart",

    reorderQuantityLimitToast(productName, availableQuantity) {
      const quantity = Number(availableQuantity);

      if (!Number.isFinite(quantity) || quantity <= 0) {
        return `“${productName}” is no longer available.`;
      }

      return (
        `Only ${quantity} ${quantity === 1 ? "item is" : "items are"} ` +
        `available for “${productName}”. Change the quantity to ${quantity} or less.`
      );
    },

    pageOnly(page) {
      return `Page ${page}`;
    },

    pageSummary(page, totalPages, totalCount) {
      return `Page ${page} of ${totalPages} · ${totalCount} total orders`;
    },

    startDateMin(minDate) {
      return `Start date cannot be earlier than ${minDate}.`;
    },

    endDateMin(minDate) {
      return `End date cannot be earlier than ${minDate}.`;
    },

    startDateFuture: "Start date cannot be in the future.",
    endDateFuture: "End date cannot be in the future.",
    startDateAfterEnd: "Start date must be earlier than or equal to end date.",

    needsReviewSummary(count) {
      return `${pluralize(count, "item", "items")} need review`;
    },

    alternativeOptionsSummary(count) {
      return `${pluralize(count, "alternative option", "alternative options")} available`;
    },

    unavailableSummary(count) {
      return `${pluralize(count, "item", "items")} currently unavailable`;
    },

    selectedBadge(count) {
      return `${count} selected`;
    },

    skippedBadge(count) {
      return `${count} skipped`;
    },

    needsReviewBadge(count) {
      return `${count} need review`;
    },

    saveAmount(amount) {
      return `You save ${amount}`;
    },

    matchBadge(matchLabel) {
      return `${matchLabel} match`;
    },

    requestedAvailableNow(requested, available, reason = "") {
      return `Requested ${requested} · available now ${available}.${reason ? ` ${reason}` : ""}`;
    },

    priceChanged(originalPrice, currentPrice) {
      return `${this.priceChangedPrefix} ${originalPrice} to ${currentPrice}.`;
    },

    producerChanged(originalProducer, currentProducer) {
      return `${this.producerChangedPrefix}: ${originalProducer} → ${currentProducer}.`;
    },

    wholesaleActiveNextTier(minQuantity, unitPrice) {
      return `Next tier: buy ${minQuantity}+ for ${unitPrice} each.`;
    },

    wholesaleActiveQualified:
      "Current quantity qualifies for wholesale pricing.",

    wholesaleUnlock(minQuantity, unitPrice, difference) {
      return `Buy ${minQuantity}+ for ${unitPrice} each. Add ${difference} more to unlock it.`;
    },

    availableNow(quantity) {
      return `Available now: ${quantity}`;
    },

    originallyOrdered(quantity) {
      return `Originally ordered: ${quantity}`;
    },

    selectedQuantity(quantity) {
      return `${quantity}`;
    },

    producerLine(name) {
      return `Producer: ${name}`;
    },

    quantityAdded(quantity) {
      return `Quantity added: ${quantity}`;
    },

    requestedReason(requested, reason) {
      return `Requested: ${requested} · Reason: ${reason}`;
    },

    requestedAdded(requested, added) {
      return `Requested: ${requested} · Added: ${added}`;
    },

    availableWithChoiceBody: "This item will not be added to the cart.",

    resultBadge(count, label) {
      return `${count} ${label}`;
    },

    getErrorPayload(error) {
      return (
        error?.payload ||
        error?.data ||
        error?.response?.data ||
        error?.details ||
        null
      );
    },

    getStructuredError(error) {
      const payload = this.getErrorPayload(error);

      if (!payload || typeof payload !== "object") {
        return null;
      }

      return payload.error || payload;
    },

    getStructuredErrorCode(error) {
      return this.getStructuredError(error)?.code || "";
    },

    getStructuredErrorData(error) {
      return this.getStructuredError(error)?.data || {};
    },

    getBackendMessage(error, fallback) {
      const structuredError = this.getStructuredError(error);
      return (
        structuredError?.message ||
        window.AppApiErrors.fromError(error, fallback)
      );
    },

    getOrderFilterError(error, fallback) {
      const code = this.getStructuredErrorCode(error);

      if (code === "order_filter_start_date_future") {
        return this.startDateFuture;
      }

      if (code === "order_filter_end_date_future") {
        return this.endDateFuture;
      }

      if (code === "order_filter_invalid_date_range") {
        return this.startDateAfterEnd;
      }

      if (code === "order_filter_invalid_date_format") {
        return "Use the date format YYYY-MM-DD.";
      }

      if (code === "order_filter_invalid_integer") {
        return "One filter value is invalid. Check the selected filters and try again.";
      }

      return this.getBackendMessage(error, fallback);
    },

    getReorderItemReason(item) {
      const code = item?.reason_code || "";
      const data = item?.reason_data || {};

      if (code === "cart_stock_limit_exceeded") {
        const productName =
          data.product_name ||
          item?.product_name ||
          this.productFallback ||
          "this item";

        const quantityInCart = formatQuantity(data.quantity_in_cart ?? 0);
        const requestedQuantity = formatQuantity(
          data.requested_quantity ?? item?.requested_quantity ?? 0,
        );
        const requestedTotalQuantity = formatQuantity(
          data.requested_total_quantity ?? 0,
        );
        const availableStock = formatQuantity(
          data.available_stock ?? data.max_allowed_quantity ?? 0,
        );
        const maxAddableQuantity = Number(data.max_addable_quantity ?? 0);

        if (maxAddableQuantity <= 0) {
          return (
            `“${productName}” is already in the cart with quantity ${quantityInCart}. ` +
            `No more can be added because only ${availableStock} are available in total. ` +
            `Please reduce the quantity in the cart before reordering.`
          );
        }

        return (
          `“${productName}” is already in the cart with quantity ${quantityInCart}. ` +
          `Adding ${requestedQuantity} more would make the cart quantity ${requestedTotalQuantity}, ` +
          `but only ${availableStock} are available in total. ` +
          `Please reduce this reorder quantity to ${formatQuantity(maxAddableQuantity)} or update the cart first.`
        );
      }

      if (code === "reorder_quantity_reduced") {
        const requested = data.requested_quantity ?? item?.requested_quantity;
        const added = data.added_quantity ?? item?.added_quantity;
        return `Requested ${requested}, but only ${added} can be added now.`;
      }

      if (code === "reorder_item_unavailable") {
        return "This item cannot be reordered right now.";
      }

      if (code === "reorder_cart_add_failed") {
        return "This item could not be added to the cart.";
      }

      return item?.reason || this.unavailable;
    },

    getLoadError(error) {
      return this.getOrderFilterError(error, this.loadFailed);
    },

    getDetailLoadError(error) {
      return this.getBackendMessage(error, this.detailLoadFailed);
    },

    getPreviewError(error) {
      const code = this.getStructuredErrorCode(error);

      if (code === "order_not_reorderable") {
        return this.reorderNotAvailable;
      }

      if (
        code === "invalid_reorder_selection_item" ||
        code === "duplicate_reorder_selection_item"
      ) {
        return "The reorder selection is no longer valid. Refresh the planner and try again.";
      }

      return this.getBackendMessage(error, this.previewFailed);
    },

    getReorderError(error) {
      const code = this.getStructuredErrorCode(error);

      if (code === "order_not_reorderable") {
        return this.reorderNotAvailable;
      }

      if (
        code === "invalid_reorder_selection_item" ||
        code === "duplicate_reorder_selection_item"
      ) {
        return "The reorder selection is no longer valid. Refresh the planner and try again.";
      }

      return this.getBackendMessage(error, this.reorderFailed);
    },
  };
})();
