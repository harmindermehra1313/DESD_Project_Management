document.addEventListener("DOMContentLoaded", () => {
    loadProducerContent();
});

let recipePage = 1;
let storyPage = 1;
const ITEMS_PER_PAGE = 10;


function renderPagination(container, totalItems, currentPage, onPageChange) {
    const totalPages = Math.ceil(totalItems / ITEMS_PER_PAGE);
    container.innerHTML = "";

    // Prev button
    const prev = document.createElement("button");
    prev.textContent = "Prev";
    prev.disabled = currentPage === 1;
    prev.onclick = () => onPageChange(currentPage - 1);
    container.appendChild(prev);

    // Page numbers
    for (let i = 1; i <= totalPages; i++) {
        const btn = document.createElement("button");
        btn.textContent = i;
        btn.className = i === currentPage ? "active" : "";
        btn.onclick = () => onPageChange(i);
        container.appendChild(btn);
    }

    // Next button
    const next = document.createElement("button");
    next.textContent = "Next";
    next.disabled = currentPage === totalPages;
    next.onclick = () => onPageChange(currentPage + 1);
    container.appendChild(next);
}

function loadProducerContent() {
    fetch("/community/api/producer/content/")
        .then(res => res.json())
        .then(data => {
            renderRecipes(data.recipes);
            renderStories(data.stories);
            attachRowClickEvents();
        })
        .catch(err => console.error("Failed to load content:", err));
}

/* ---------------------------
   RENDER RECIPES
---------------------------- */
function renderRecipes(recipes) {
    const start = (recipePage - 1) * ITEMS_PER_PAGE;
    const end = start + ITEMS_PER_PAGE;
    const pageItems = recipes.slice(start, end);

    const table = document.querySelector("#dpRecipesTableBody");
    table.innerHTML = "";

    pageItems.forEach(r => {
        const row = document.createElement("tr");
        row.classList.add("dp-row");
        row.dataset.type = "recipe";
        row.dataset.id = r.id;

        row.innerHTML = `
            <td><img src="${r.image}" class="dp-thumb-sm"></td>
            <td>${r.title}</td>
            <td>${r.season}</td>
            <td>${r.status_display}</td>
            <td>${r.created_at}</td>
        `;

        table.appendChild(row);
    });

    // Render pagination
    renderPagination(
        document.getElementById("dpRecipePagination"),
        recipes.length,
        recipePage,
        (newPage) => {
            recipePage = newPage;
            renderRecipes(recipes);
            attachRowClickEvents();
        }
    );
}



/* ---------------------------
   RENDER STORIES
---------------------------- */
function renderStories(stories) {
    const start = (storyPage - 1) * ITEMS_PER_PAGE;
    const end = start + ITEMS_PER_PAGE;
    const pageItems = stories.slice(start, end);

    const table = document.querySelector("#dpStoriesTableBody");
    if (!table) return;

    table.innerHTML = "";

    stories.forEach(s => {
        const row = document.createElement("tr");
        row.classList.add("dp-row");
        row.dataset.type = "story";
        row.dataset.id = s.id;

        row.innerHTML = `
            <td><img src="${s.image}" class="dp-thumb-sm"></td>
            <td>${s.title}</td>
            <td>${s.status_display}</td>
            <td>${s.created_at}</td>
        `;

        table.appendChild(row);
    });

    // Render pagination
    renderPagination(
        document.getElementById("dpStoryPagination"),
        stories.length,
        storyPage,
        (newPage) => {
            recipePage = newPage;
            renderstoies(recipes);
            attachRowClickEvents();
        }
    );
}


/* ---------------------------
   CLICK EVENTS FOR PREVIEW
---------------------------- */
function attachRowClickEvents() {
    const rows = document.querySelectorAll(".dp-row");

    const previewCard = document.getElementById("dpPreviewCard");
    const previewImage = document.getElementById("dpPreviewImage");
    const previewTitle = document.getElementById("dpPreviewTitle");
    const previewMeta = document.getElementById("dpPreviewMeta");
    const previewDescription = document.getElementById("dpPreviewDescription");
    const previewStatus = document.getElementById("dpPreviewStatus");

    const ingList = document.getElementById("dpPreviewIngredients");
    const instList = document.getElementById("dpPreviewInstructions");

    const editBtn = document.getElementById("dpEditBtn");
    const deleteBtn = document.getElementById("dpDeleteBtn");
    const linkedList = document.getElementById("dpPreviewLinkedProducts");

    rows.forEach(row => {
        row.addEventListener("click", () => {
            const type = row.dataset.type;
            const id = row.dataset.id;
            
            fetch(`/community/api/${type}/${id}/`)
                .then(res => res.json())
                .then(data => {
                    previewCard.style.display = "block";

                    // Basic fields
                    previewImage.src = data.image;
                    previewTitle.textContent = data.title;
                    previewMeta.textContent = data.meta;
                    previewDescription.textContent = data.description;
                    previewStatus.textContent = data.status;
                    // Set RECIPE / STORY tag
                    const typeTag = document.getElementById("dpPreviewType");
                    typeTag.textContent = type === "recipe" ? "RECIPE" : "STORY";

                    // Show/hide sections based on type
                    if (type === "story") {
                        document.querySelector("[data-section='ingredients']").style.display = "none";
                        document.querySelector("[data-section='instructions']").style.display = "none";
                        document.querySelector("[data-section='linked']").style.display = "none";
                    } else {
                        document.querySelector("[data-section='ingredients']").style.display = "block";
                        document.querySelector("[data-section='instructions']").style.display = "block";
                        document.querySelector("[data-section='linked']").style.display = "block";
                    }

                    // Ingredients
                    ingList.innerHTML = "";
                    if (data.ingredients) {
                        data.ingredients.forEach(item => {
                            const li = document.createElement("li");
                            li.textContent = item;
                            ingList.appendChild(li);
                        });
                    }

                    // Instructions
                    instList.innerHTML = "";
                    if (data.instructions) {
                        data.instructions.forEach(step => {
                            const li = document.createElement("li");
                            li.textContent = step;
                            instList.appendChild(li);
                        });
                    }

                    // Linked products
                    linkedList.innerHTML = "";
                    if (data.linked_products) {
                        data.linked_products.forEach(p => {
                            const li = document.createElement("li");
                            li.textContent = p.name;
                            linkedList.appendChild(li);
                        });
                    }

                    // Buttons
                    editBtn.href = data.edit_url;
                    deleteBtn.href = data.delete_url;
                    // Auto-scroll on mobile
                    if (window.innerWidth <= 768) {
                        document.querySelector(".dp-preview-area").scrollIntoView({
                            behavior: "smooth",
                            block: "start"
                        });
                    }

                });
        });
    });

}
