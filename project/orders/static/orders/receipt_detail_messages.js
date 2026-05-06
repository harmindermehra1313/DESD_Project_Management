// orders/static/orders/receipt_detail_messages.js
(function () {
  window.ReceiptDetailMessages = {
    dash: "-",

    loadFailed: "We couldn't load this receipt right now.",
    addressUnavailable: "Address not available",
    paymentUnavailable: "Not available",
    noItems: "No receipt items available.",
    fulfilmentUnavailable: "Fulfilment details are not available.",

    orderNumberLabel: "Order Number",
    orderDateLabel: "Order Date",
    statusLabel: "Status",
    customerLabel: "Customer",
    paymentLabel: "Payment",

    productLabel: "Product",
    producerLabel: "Producer",
    quantityLabel: "Quantity",
    activeQuantityLabel: "Active quantity",
    originalQuantityLabel: "Original quantity",
    cancelledRefundedQuantityLabel: "Cancelled/refunded",

    originalUnitPriceLabel: "Original Unit Price",
    perUnitDiscountLabel: "Per Unit Discount",
    paidUnitPriceLabel: "Paid Unit Price",

    vatLabel: "VAT",
    activeVatLabel: "VAT on active items",
    refundedVatLabel: "Refunded VAT",

    lineTotalLabel: "Line Total",
    lineTotalIncludingVatLabel: "Line Total (incl. VAT)",

    totalSavedLabel: "Total saved",
    eachSuffix: "each",
    includingVatSuffix: "incl. VAT",

    collectionAddressLabel: "Collection address",
    deliveryAddressLabel: "Delivery address",
    unknownProducer: "Unknown producer",

    dateLabel: "Date",
    timeSlotLabel: "Time Slot",
    specialInstructionsLabel: "Special Instructions",

    subtotalLabel: "Subtotal before VAT",
    discountLabel: "Discount",
    cancelledRefundedTotalLabel: "Cancelled/refunded value",
    finalTotalLabel: "Final Total",
    finalTotalIncludingVatLabel: "Final amount due (incl. VAT)",

    fullyCancelledLabel: "Fully cancelled",
    partiallyCancelledLabel: "Partially cancelled",
    noneLabel: "None",

    itemSingularLabel: "item",
    itemPluralLabel: "items",

    cancelledProducerSectionMessage:
      "This producer section was cancelled. Any cancelled/refunded items are shown in the items table.",

    totalSaved(amount) {
      return `${this.totalSavedLabel}: ${amount}`;
    },

    quantityBreakdown(item) {
      const activeQuantity = Number(item.active_quantity ?? item.quantity ?? 0);
      const originalQuantity = Number(item.original_quantity ?? activeQuantity);
      const cancelledQuantity = Number(item.cancelled_quantity ?? 0);

      const lines = [
        `${this.activeQuantityLabel}: ${activeQuantity}`,
        `${this.originalQuantityLabel}: ${originalQuantity}`,
      ];

      if (cancelledQuantity > 0) {
        lines.push(
          `${this.cancelledRefundedQuantityLabel}: ${cancelledQuantity}`,
        );
      }

      return lines;
    },

    cancelledRefundedAmount(cancelledQuantity, formattedAmount) {
      if (cancelledQuantity <= 0) {
        return this.noneLabel;
      }

      const itemLabel =
        cancelledQuantity === 1 ? this.itemSingularLabel : this.itemPluralLabel;

      return `${cancelledQuantity} ${itemLabel}, ${formattedAmount} removed`;
    },

    getAddressLabel(isCollection) {
      return isCollection
        ? this.collectionAddressLabel
        : this.deliveryAddressLabel;
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

    getBackendMessage(error, fallback) {
      const structuredError = this.getStructuredError(error);

      return (
        structuredError?.message ||
        window.AppApiErrors.fromError(error, fallback)
      );
    },

    getLoadError(error) {
      const structuredError = this.getStructuredError(error);

      if (structuredError?.code === "receipt_not_available") {
        return (
          structuredError.message || "Receipt is not available for this order."
        );
      }

      return this.getBackendMessage(error, this.loadFailed);
    },
  };
})();
