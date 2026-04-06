// products/static/js/product_detail_messages.js
(function () {
  window.ProductDetailMessages = {
    invalidProductId: "This product could not be opened.",
    loadFailed: "We couldn't load this product right now.",
    unavailable: "This product is not available right now.",
    missingInventory: "This product cannot be added to your cart right now.",
    cartUnavailable: "The cart is unavailable right now. Please refresh and try again.",
    addedToCart: "Added to cart.",
    addFailed: "We couldn't add this item to your cart. Please try again.",

    getUnavailableMessage(productData, formatDate) {
      if (!productData) return this.unavailable;

      if (productData.is_expired) {
        const label = productData.expiry_type_label || "Expiry date";
        const dateText = productData.expiry_date
          ? formatDate(productData.expiry_date)
          : null;

        return dateText
          ? `This item has expired. ${label} was ${dateText}.`
          : "This item has expired and cannot be added to your cart.";
      }

      return this.unavailable;
    },

    getLoadError(error) {
      return window.AppApiErrors.fromError(error, this.loadFailed);
    },

    getAddError(error, productData, formatDate) {
      const raw = window.AppApiErrors.fromError(error, this.addFailed);

      if (/expired/i.test(raw)) {
        return this.getUnavailableMessage(productData, formatDate);
      }

      return raw;
    },
  };
})();