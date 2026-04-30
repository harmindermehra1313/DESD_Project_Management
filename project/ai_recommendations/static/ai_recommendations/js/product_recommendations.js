(function () {
  function getCookie(name) {
    const cookies = document.cookie ? document.cookie.split(";") : [];

    for (const cookie of cookies) {
      const trimmedCookie = cookie.trim();

      if (trimmedCookie.startsWith(`${name}=`)) {
        return decodeURIComponent(trimmedCookie.substring(name.length + 1));
      }
    }

    return "";
  }

  function getCsrfToken(section) {
    const tokenInput = section.querySelector("[name='csrfmiddlewaretoken']");

    if (tokenInput) {
      return tokenInput.value;
    }

    return getCookie("csrftoken");
  }

  async function trackProductEvent(productId, eventType, csrfToken) {
    if (!productId) {
      return;
    }

    await fetch("/ai-recommendations/track/", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken || getCookie("csrftoken"),
      },
      body: JSON.stringify({
        product_id: Number(productId),
        event_type: eventType,
      }),
    });
  }

  function createTextElement(tagName, className, text) {
    const element = document.createElement(tagName);
    element.className = className;
    element.textContent = text || "";
    return element;
  }

  function createRecommendationCard(product) {
    const card = document.createElement("article");
    card.className = "ai-rec-card";

    if (product.image_url) {
      const image = document.createElement("img");
      image.className = "ai-rec-card__image";
      image.src = product.image_url;
      image.alt = product.name;
      card.appendChild(image);
    }

    const body = document.createElement("div");
    body.className = "ai-rec-card__body";

    body.appendChild(
      createTextElement("h3", "ai-rec-card__title", product.name),
    );

    body.appendChild(
      createTextElement(
        "p",
        "ai-rec-card__meta",
        `${product.category || "Product"}${
          product.product_type ? ` • ${product.product_type}` : ""
        }`,
      ),
    );
    body.appendChild(
      createTextElement(
        "p",
        "ai-rec-card__producer",
        `Sold by ${product.producer || "Local producer"}`,
      ),
    );
    body.appendChild(
      createTextElement(
        "p",
        "ai-rec-card__price",
        `£${product.price} / ${product.unit}`,
      ),
    );

    body.appendChild(
      createTextElement(
        "p",
        "ai-rec-card__reason",
        `Why recommended: ${product.reason}`,
      ),
    );

    const link = document.createElement("a");
    link.className = "btn btn-primary ai-rec-card__button";
    link.href = product.detail_url;
    link.textContent = "View product";

    body.appendChild(link);
    card.appendChild(body);

    return card;
  }

  async function loadRecommendations(section) {
    const productId = section.dataset.productId;
    const grid = section.querySelector("[data-ai-recommendations-grid]");
    const status = section.querySelector("[data-ai-recommendations-status]");
    const csrfToken = getCsrfToken(section);

    if (!productId || !grid) {
      section.remove();
      return;
    }

    try {
      try {
        await trackProductEvent(productId, "view", csrfToken);
      } catch (error) {
        // Tracking failure should not stop recommendation loading.
      }

      const response = await fetch(
        `/ai-recommendations/products/${productId}/`,
        {
          credentials: "same-origin",
        },
      );

      if (!response.ok) {
        throw new Error("Recommendations could not be loaded.");
      }

      const payload = await response.json();
      grid.innerHTML = "";

      if (!payload.results || payload.results.length === 0) {
        section.remove();
        return;
      }

      for (const product of payload.results) {
        grid.appendChild(createRecommendationCard(product));
      }

      if (status) {
        status.textContent = "";
      }

      section.classList.remove("d-none");
    } catch (error) {
      section.remove();
    }
  }

  window.AIRecommendations = {
    trackProductView(productId) {
      return trackProductEvent(productId, "view");
    },
    trackAddToCart(productId) {
      return trackProductEvent(productId, "addtocart");
    },
  };

  document.addEventListener("DOMContentLoaded", () => {
    const section = document.querySelector("[data-ai-recommendations]");

    if (section) {
      loadRecommendations(section);
    }
  });
})();
