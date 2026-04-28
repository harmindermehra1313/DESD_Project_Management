// products/static/js/product_detail_messages.js
(function () {
  function titleCaseFromConstant(value) {
    return String(value || "")
      .toLowerCase()
      .split("_")
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
  }

  window.ProductDetailMessages = {
    dash: "—",
    unknownLabel: "Unknown",
    availableStatusLabel: "Available",
    unavailableStatusLabel: "Unavailable",
    expiryLabel: "Expiry",
    invalidProductId: "This product could not be opened.",
    loadFailed: "We couldn't load this product right now.",
    unavailable: "This product is not available right now.",
    missingInventory: "This product cannot be added to your cart right now.",
    cartUnavailable:
      "The cart is unavailable right now. Please refresh and try again.",
    addedToCart: "Added to cart.",
    addFailed: "We couldn't add this item to your cart. Please try again.",
    addToCartLabel: "Add to cart",
    unavailableButtonLabel: "Unavailable",
    uncategorized: "Uncategorized",
    unknownProducer: "Unknown producer",
    noDescription: "No description available.",
    noKnownAllergens: "No known allergens.",
    productImageAlt: "Product image",
    certifiedOrganic: "Certified organic",
    wholesaleLabel: "Wholesale",
    wholesalePriceActiveTitle: "Wholesale price active",
    wholesalePricingAvailableTitle: "Wholesale pricing available",
    surplusReductionTitle: "Surplus reduction",
    surplusWholesaleAppliedNote:
      "This item has a surplus reduction, but wholesale pricing is currently applied.",
    surplusDiscountAppliedNote: "Discount applied to help clear excess stock.",
    bestAvailableTierUnlocked: "Best available tier unlocked.",
    increaseQuantityHint: "Increase quantity to unlock this price.",
    notCurrentlyReachable: "Not currently reachable with available stock.",

    getExpiryLabel(productData) {
      return productData?.expiry_type_label || this.expiryLabel;
    },

    getBadgeLabel(productData, purchasable) {
      return (
        productData?.availability_label ||
        (purchasable ? this.availableStatusLabel : this.unavailableStatusLabel)
      );
    },

    getButtonLabel(productData, purchasable) {
      return (
        productData?.add_to_cart_button_label ||
        (purchasable ? this.addToCartLabel : this.unavailableButtonLabel)
      );
    },

    getStockText(productData, stock) {
      return productData?.stock_message || this.stockRemaining(stock);
    },

    stockRemaining(stock) {
      return `${stock} left`;
    },

    saveAmount(amount) {
      return `Save ${amount}`;
    },

    percentOff(percent) {
      return `${percent}% off`;
    },

    payingPerUnit(price) {
      return `You're paying ${price} per unit.`;
    },

    savePerUnit(amount) {
      return `Save ${amount} per unit.`;
    },

    nextTier(minQuantity, price) {
      return `Next tier at ${minQuantity}+ units: ${price} per unit.`;
    },

    wholesaleUnlock(minQuantity, price) {
      return `Buy ${minQuantity}+ to pay ${price} per unit.`;
    },

    wholesaleTier(minQuantity, price) {
      return `Wholesale tier: ${minQuantity}+ units at ${price}`;
    },

    titleCaseStatus(status) {
      return titleCaseFromConstant(status);
    },

    getOrganicStatusMarkup(status) {
      if (!status) return this.dash;
      if (status === "CERTIFIED") {
        return `<span class="badge rounded-pill bg-success">${this.certifiedOrganic}</span>`;
      }
      return `<span class="badge rounded-pill text-bg-secondary">${titleCaseFromConstant(status)}</span>`;
    },

    getImageAlt(name) {
      return name || this.productImageAlt;
    },

    getUnavailableMessage(productData, formatDate) {
      if (!productData) return this.unavailable;

      if (productData.is_expired) {
        const label = this.getExpiryLabel(productData);
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

    getCartStockLimitMessage(error) {
      const structuredError = this.getStructuredError(error);

      if (structuredError?.code !== "cart_stock_limit_exceeded") {
        return null;
      }

      const data = structuredError.data || structuredError.details || {};

      const availableStock = this.toNonNegativeInteger(data.available_stock);
      const quantityInCart = this.toNonNegativeInteger(data.quantity_in_cart);
      const maxAddableQuantity = this.toNonNegativeInteger(
        data.max_addable_quantity,
      );

      if (
        Number.isInteger(availableStock) &&
        Number.isInteger(quantityInCart) &&
        Number.isInteger(maxAddableQuantity)
      ) {
        if (maxAddableQuantity > 0) {
          return (
            `${availableStock} items are available. ` +
            `${quantityInCart} are already in the cart, so a maximum of ` +
            `${maxAddableQuantity} more can be added.`
          );
        }

        return (
          `${availableStock} items are available and ` +
          `${quantityInCart} are already in the cart. ` +
          "No more can be added."
        );
      }

      return (
        structuredError.message ||
        "The requested quantity exceeds available stock."
      );
    },

    getAddError(error, productData, formatDate) {
      const structuredError = this.getStructuredError(error);

      if (structuredError?.code === "cart_stock_limit_exceeded") {
        return this.getCartStockLimitMessage(error);
      }

      const raw = window.AppApiErrors.fromError(error, this.addFailed);

      if (/expired/i.test(raw)) {
        return this.getUnavailableMessage(productData, formatDate);
      }

      return raw;
    },
  };
})();
