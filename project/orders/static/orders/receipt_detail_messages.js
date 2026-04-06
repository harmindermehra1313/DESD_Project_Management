// orders/static/orders/receipt_detail_messages.js
(function () {
  window.ReceiptDetailMessages = {
    loadFailed: "We couldn't load this receipt right now.",

    getLoadError(error) {
      return window.AppApiErrors.fromError(error, this.loadFailed);
    },
  };
})();