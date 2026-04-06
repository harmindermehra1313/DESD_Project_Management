// carts/static/carts/cart_page_messages.js
(function () {
  window.CartPageMessages = {
    dash: "—",
    productFallback: "Product",
    cartApiMissing: "The cart is unavailable right now. Please refresh the page.",
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

    getBlockedMessage(product) {
      if (product?.is_expired) return this.expiredItem;
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
