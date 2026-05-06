// carts/static/carts/cart_page_messages.js
(function () {
  window.CartPageMessages = {
    dash: "—",
    productFallback: "Product",
    cartApiMissing:
      "The cart is unavailable right now. Please refresh the page.",
    loadFailed: "We couldn't load your cart right now.",
    updateFailed: "We couldn't update that item right now.",
    removeFailed: "We couldn't remove that item right now.",
    updatedQuantity(qty) {
      return `Quantity updated to ${qty}.`;
    },
    removedItem(name) {
      return `Removed “${name}” from your cart.`;
    },
    blockedCheckout:
      "Some items are expired or unavailable. Remove them to continue to checkout.",
    unavailableItem: "This item is currently unavailable.",
    expiredItem: "This product has expired. Please remove it from your cart.",
    expiredBadge: "Expired",
    outOfStockBadge: "Out of stock",
    wholesaleBadge: "Wholesale",
    surplusBadge: "Surplus reduction",
    expiryLabel: "Expiry",
    unitLabelPrefix: "Unit",
    lineLabelPrefix: "Line",
    removeButton: "Remove",
    notSpecified: "Not specified",
    cartTitle: "Cart",
    checkoutPath: "/orders/checkout",
    minimumQuantityTitle: "Quantity cannot be reduced",
    surplusReasonLabel: "Reason for reduction",
    surplusReasonFallback: "Surplus stock",

    getBlockedMessage(product) {
      if (product?.stock_message) {
        return product.stock_message;
      }

      if (product?.is_expired) {
        return this.expiredItem;
      }

      return this.unavailableItem;
    },

    getExpiryLabel(product) {
      return product?.expiry_type_label || this.expiryLabel;
    },

    saveWithWholesale(amount) {
      return `You save ${amount} with wholesale pricing`;
    },

    saveWithSurplus(amount) {
      return `Surplus reduction: you save ${amount}`;
    },

    unitLabel(amount) {
      return `${this.unitLabelPrefix}: ${amount}`;
    },

    lineLabel(amount) {
      return `${this.lineLabelPrefix}: ${amount}`;
    },
    minimumQuantityMessage(name) {
      return `“${name}” already has the minimum quantity of 1. Use Remove to delete it from your cart.`;
    },

    getSurplusReason(note) {
      const reason = String(note ?? "").trim();

      if (!reason || reason.toLowerCase() === "none") {
        return this.surplusReasonFallback;
      }

      return reason;
    },

    removeConfirm(name) {
      return `Remove “${name}” from your cart?`;
    },

    subtotalBeforeDiscounts: "Subtotal (before discounts)",
    wholesaleSavings: "Wholesale savings",
    surplusSavings: "Surplus savings",
    savingsIntro: "Nice!",
    savingsMessage(total) {
      return `You saved ${total} with discounts.`;
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

    toNonNegativeInteger(value) {
      if (value === null || value === undefined || value === "") {
        return null;
      }

      const number = Number(value);

      if (!Number.isFinite(number) || number < 0) {
        return null;
      }

      return Math.floor(number);
    },

    inventoryLimitMessage(name, availableQty) {
      const qty = this.toNonNegativeInteger(availableQty);

      if (!Number.isInteger(qty) || qty <= 0) {
        return `“${name}” is no longer available. Please remove it from your cart.`;
      }

      return (
        `Only ${qty} ${qty === 1 ? "item is" : "items are"} available ` +
        `for “${name}”. Change the quantity to ${qty} or less.`
      );
    },

    getStockLimitMessage(error, product) {
      const structuredError = this.getStructuredError(error);

      if (structuredError?.code !== "cart_stock_limit_exceeded") {
        return null;
      }

      const data = structuredError.data || structuredError.details || {};
      const name = data.product_name || product?.name || this.productFallback;

      const availableStock = this.toNonNegativeInteger(data.available_stock);
      const maxAllowedQuantity =
        this.toNonNegativeInteger(data.max_allowed_quantity) ?? availableStock;

      if (!Number.isInteger(maxAllowedQuantity) || maxAllowedQuantity <= 0) {
        return `“${name}” is no longer available. Please remove it from your cart.`;
      }

      return (
        `Only ${maxAllowedQuantity} ` +
        `${maxAllowedQuantity === 1 ? "item is" : "items are"} available ` +
        `for “${name}”. Change the quantity to ${maxAllowedQuantity} or less.`
      );
    },

    isInventoryLimitError(error) {
      return (
        this.getStructuredError(error)?.code === "cart_stock_limit_exceeded"
      );
    },

    getRowUpdateError(error, product) {
      const stockLimitMessage = this.getStockLimitMessage(error, product);

      if (stockLimitMessage) {
        return stockLimitMessage;
      }

      const raw = window.AppApiErrors.fromError(error, this.updateFailed);

      if (/expired/i.test(raw)) {
        return this.getBlockedMessage(product);
      }

      return raw;
    },
    getLoadError(error) {
      return window.AppApiErrors.fromError(error, this.loadFailed);
    },

    getUpdateError(error, product) {
      const raw = window.AppApiErrors.fromError(error, this.updateFailed);
      return /expired/i.test(raw) ? this.getBlockedMessage(product) : raw;
    },

    getRemoveError(error) {
      return window.AppApiErrors.fromError(error, this.removeFailed);
    },
  };
})();
