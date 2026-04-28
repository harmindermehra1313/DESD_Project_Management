// orders/static/orders/receipt_detail_messages.js
(function () {
  window.ReceiptDetailMessages = {
    dash: "-",
    loadFailed: "We couldn't load this receipt right now.",
    addressUnavailable: "Address not available",
    orderNumberLabel: "Order Number",
    orderDateLabel: "Order Date",
    statusLabel: "Status",
    customerLabel: "Customer",
    paymentLabel: "Payment",
    paymentUnavailable: "Not available",
    noItems: "No receipt items available.",
    fulfilmentUnavailable: "Fulfilment details are not available.",
    productLabel: "Product",
    producerLabel: "Producer",
    quantityLabel: "Quantity",
    originalUnitPriceLabel: "Original Unit Price",
    perUnitDiscountLabel: "Per Unit Discount",
    vatLabel: "VAT",
    paidUnitPriceLabel: "Paid Unit Price",
    lineTotalLabel: "Line Total",
    totalSavedLabel: "Total saved",
    eachSuffix: "each",
    collectionAddressLabel: "Collection address",
    deliveryAddressLabel: "Delivery address",
    unknownProducer: "Unknown producer",
    dateLabel: "Date",
    timeSlotLabel: "Time Slot",
    specialInstructionsLabel: "Special Instructions",
    subtotalLabel: "Subtotal",
    discountLabel: "Discount",
    finalTotalLabel: "Final Total",

    totalSaved(amount) {
      return `${this.totalSavedLabel}: ${amount}`;
    },

    getAddressLabel(isCollection) {
      return isCollection
        ? this.collectionAddressLabel
        : this.deliveryAddressLabel;
    },

    getLoadError(error) {
      return window.AppApiErrors.fromError(error, this.loadFailed);
    },
  };
})();
