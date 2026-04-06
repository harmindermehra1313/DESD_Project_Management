// carts/static/carts/cart_page_messages.js
(function () {
  window.CartPageMessages = {
    cartApiMissing: "The cart is unavailable right now. Please refresh the page.",
    loadFailed: "We couldn't load your cart right now.",
    updateFailed: "We couldn't update that item right now.",
    removeFailed: "We couldn't remove that item right now.",
    updatedQuantity(qty) {
      return `Quantity updated to ${qty}.`;
    },
    removedItem(name) {
      return `Removed ${name} from your cart.`;
    },
    blockedCheckout: "Some items are expired or unavailable. Remove them to continue to checkout.",
    unavailableItem: "This item is currently unavailable.",
    expiredItem: "This product has expired. Please remove it from your cart.",

    getBlockedMessage(product) {
      if (product?.is_expired) return this.expiredItem;
      return this.unavailableItem;
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