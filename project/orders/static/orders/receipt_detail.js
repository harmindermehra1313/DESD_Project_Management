const M = window.ReceiptDetailMessages;
const orderId = window.RECEIPT_ORDER_ID;
const RECEIPT_DETAIL_API_URL = `/api/orders/${orderId}/receipt/`;
const RECEIPT_DOWNLOAD_API_URL = `/api/orders/${orderId}/receipt/download/`;

document.addEventListener("DOMContentLoaded", () => {
  bindReceiptEvents();
  loadReceipt();
});

function bindReceiptEvents() {
  const downloadBtn = document.getElementById("downloadReceiptBtn");

  if (downloadBtn) {
    downloadBtn.addEventListener("click", () => {
      window.location.href = RECEIPT_DOWNLOAD_API_URL;
    });
  }
}

async function loadReceipt() {
  const loadingEl = document.getElementById("receiptLoading");
  const errorEl = document.getElementById("receiptError");
  const contentEl = document.getElementById("receiptContent");

  showReceiptLoading();

  try {
    const response = await fetch(RECEIPT_DETAIL_API_URL, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
    });

    if (!response.ok) {
      throw new Error(await parseErrorMessage(response, M.loadFailed));
    }

    const receipt = await response.json();

    renderReceiptSummary(receipt);
    renderReceiptItems(receipt.items || []);
    renderReceiptFulfilment(receipt.producer_breakdown || []);
    renderReceiptTotals(receipt.totals || {});

    if (loadingEl) loadingEl.classList.add("d-none");
    if (errorEl) {
      errorEl.classList.add("d-none");
      errorEl.textContent = "";
    }
    if (contentEl) contentEl.classList.remove("d-none");
  } catch (error) {
    if (loadingEl) loadingEl.classList.add("d-none");
    if (contentEl) contentEl.classList.add("d-none");

    if (errorEl) {
      errorEl.textContent = M.getLoadError(error);
      errorEl.classList.remove("d-none");
    }
  }
}

function showReceiptLoading() {
  document.getElementById("receiptLoading")?.classList.remove("d-none");
  document.getElementById("receiptError")?.classList.add("d-none");
  document.getElementById("receiptContent")?.classList.add("d-none");
}

async function parseErrorMessage(response, fallbackMessage) {
  return window.AppApiErrors.fromResponse(response, fallbackMessage);
}

function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatMoney(value) {
  const amount = Number(value || 0);
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
  }).format(amount);
}

function formatDate(value) {
  if (!value) return "-";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";

  return date.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatDateTime(value) {
  if (!value) return "-";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";

  return date.toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatAddress(address) {
  if (!address) {
    return `<div class="text-muted">Address not available</div>`;
  }

  const lines = [
    address.line_1,
    address.line_2,
    [address.city, address.postcode].filter(Boolean).join(" "),
  ].filter(Boolean);

  if (!lines.length) {
    return `<div class="text-muted">Address not available</div>`;
  }

  return lines.map((line) => `<div>${escapeHtml(line)}</div>`).join("");
}

function renderReceiptSummary(receipt) {
  const el = document.getElementById("receiptSummary");
  if (!el) return;

  el.innerHTML = `
    <div class="row g-3">
      <div class="col-md-3">
        <div class="border rounded p-3 h-100">
          <div class="small text-muted">Order Number</div>
          <div class="fw-semibold">${escapeHtml(receipt.order_number || "-")}</div>
        </div>
      </div>

      <div class="col-md-3">
        <div class="border rounded p-3 h-100">
          <div class="small text-muted">Order Date</div>
          <div class="fw-semibold">${formatDateTime(receipt.order_date)}</div>
        </div>
      </div>

      <div class="col-md-2">
        <div class="border rounded p-3 h-100">
          <div class="small text-muted">Status</div>
          <div class="fw-semibold">${escapeHtml(receipt.status || "-")}</div>
        </div>
      </div>

      <div class="col-md-2">
        <div class="border rounded p-3 h-100">
          <div class="small text-muted">Customer</div>
          <div class="fw-semibold">${escapeHtml(receipt.customer_name || "-")}</div>
        </div>
      </div>

      <div class="col-md-2">
        <div class="border rounded p-3 h-100">
          <div class="small text-muted">Payment</div>
          <div class="fw-semibold">${escapeHtml(receipt.payment_method_display || "Not available")}</div>
        </div>
      </div>
    </div>
  `;
}

function renderReceiptItems(items) {
  const el = document.getElementById("receiptItems");
  if (!el) return;

  if (!items.length) {
    el.innerHTML = `<div class="text-muted">No receipt items available.</div>`;
    return;
  }

  el.innerHTML = `
    <div class="table-responsive">
      <table class="table align-middle table-bordered">
        <thead class="table-light">
            <tr>
    <th>Product</th>
    <th>Producer</th>
    <th>Quantity</th>
    <th>Original Unit Price</th>
    <th>Per Unit Discount</th>
    <th>VAT</th>
    <th>Paid Unit Price</th>
    <th>Line Total</th>
  </tr>
        </thead>
        <tbody>
          ${items
            .map(
              (item) => `
            <tr>
              <td>${escapeHtml(item.product_name)}</td>
              <td>${escapeHtml(item.producer_name)}</td>
              <td>${escapeHtml(item.quantity)}</td>
              <td>${formatMoney(item.unit_price)}</td>
              <td>
  ${formatMoney(item.discount_amount)} each
  <div class="small text-muted">
    Total saved: ${formatMoney(item.line_discount)}
  </div>
</td>
              <td>${formatMoney(item.line_vat)}</td>
              <td>${formatMoney(item.final_unit_price)}</td>
              <td class="fw-semibold">${formatMoney(item.line_total)}</td>
            </tr>
          `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderReceiptFulfilment(producerBreakdown) {
  const el = document.getElementById("receiptFulfilment");
  if (!el) return;

  if (!producerBreakdown.length) {
    el.innerHTML = `<div class="text-muted">Fulfilment details are not available.</div>`;
    return;
  }

  el.innerHTML = `
    <div class="row g-3">
      ${producerBreakdown
        .map((summary) => {
          const isCollection = (summary.delivery_or_collection || "")
            .toLowerCase()
            .includes("collection");
          const date = isCollection
            ? summary.collection_date
            : summary.delivery_date;
          const timeSlot = isCollection
            ? summary.collection_time_slot
            : summary.delivery_time_slot;
          const address = isCollection
            ? summary.collection_address
            : summary.delivery_address;
          const addressLabel = isCollection
            ? "Collection address"
            : "Delivery address";

          return `
          <div class="col-12">
            <div class="border rounded p-3">
              <div class="d-flex justify-content-between align-items-start flex-wrap gap-2 mb-3">
                <div>
                  <div class="fw-semibold">${escapeHtml(summary.producer_name || "Unknown producer")}</div>
                  <div class="small text-muted">${escapeHtml(summary.delivery_or_collection || "-")}</div>
                </div>
                <span class="badge text-bg-light border">${escapeHtml(summary.status || "-")}</span>
              </div>

              <div class="row g-3">
                <div class="col-md-3">
                  <div class="small text-muted">Date</div>
                  <div class="fw-semibold">${formatDate(date)}</div>
                </div>

                <div class="col-md-3">
                  <div class="small text-muted">Time Slot</div>
                  <div class="fw-semibold">${escapeHtml(timeSlot || "-")}</div>
                </div>

                <div class="col-md-6">
                  <div class="small text-muted">${escapeHtml(addressLabel)}</div>
                  <div>${formatAddress(address)}</div>
                </div>

                <div class="col-12">
                  <div class="small text-muted">Special Instructions</div>
                  <div>${escapeHtml(summary.special_instructions || "-")}</div>
                </div>
              </div>
            </div>
          </div>
        `;
        })
        .join("")}
    </div>
  `;
}

function renderReceiptTotals(totals) {
  const el = document.getElementById("receiptTotals");
  if (!el) return;

  el.innerHTML = `
    <div class="row justify-content-end">
      <div class="col-md-5 col-lg-4">
        <div class="border rounded p-3">
          <div class="d-flex justify-content-between mb-2">
            <span class="text-muted">Subtotal</span>
            <span>${formatMoney(totals.subtotal)}</span>
          </div>
          <div class="d-flex justify-content-between mb-2">
            <span class="text-muted">Discount</span>
            <span>${formatMoney(totals.discount)}</span>
          </div>
          <div class="d-flex justify-content-between mb-2">
            <span class="text-muted">VAT</span>
            <span>${formatMoney(totals.vat)}</span>
          </div>
          <hr>
          <div class="d-flex justify-content-between fs-5 fw-bold">
            <span>Final Total</span>
            <span>${formatMoney(totals.final_total)}</span>
          </div>
        </div>
      </div>
    </div>
  `;
}
