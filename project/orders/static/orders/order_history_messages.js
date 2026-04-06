// orders/static/orders/order_history_messages.js
(function () {
  window.OrderHistoryMessages = {
    loadFailed: "We couldn't load your order history right now.",
    previewFailed: "We couldn't open the reorder planner right now.",
    reorderFailed: "We couldn't add the selected items to your cart.",
    previewTitle: "Review your items",
    successTitle: "Added to cart",
    confirmButton: "Add Selected Items to Cart",
    reorderNotAvailable: "This order cannot be reordered.",

    getLoadError(error) {
      return window.AppApiErrors.fromError(error, this.loadFailed);
    },

    getPreviewError(error) {
      const raw = window.AppApiErrors.fromError(error, this.previewFailed);
      if (/cannot be reordered/i.test(raw)) return this.reorderNotAvailable;
      return raw;
    },

    getReorderError(error) {
      const raw = window.AppApiErrors.fromError(error, this.reorderFailed);
      if (/cannot be reordered/i.test(raw)) return this.reorderNotAvailable;
      return raw;
    },
  };
})();