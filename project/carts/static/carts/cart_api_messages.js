// carts/static/carts/cart_api_messages.js
(function () {
  window.CartApiMessages = {
    csrfMissing: "Your session could not be verified. Refresh the page and try again.",
    requestFailed(status) {
      return status ? `Request failed (${status}). Please try again.` : "Request failed. Please try again.";
    },
    invalidInventoryId: "This cart item is invalid.",
    invalidQuantity: "Please enter a valid quantity.",
  };
})();