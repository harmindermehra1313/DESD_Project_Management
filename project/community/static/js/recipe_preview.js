document.addEventListener("DOMContentLoaded", () => {
    const input = document.getElementById("imageInput");
    const preview = document.getElementById("previewImage");

    if (!input || !preview) return;

    input.addEventListener("change", (e) => {
        const file = e.target.files[0];

        if (file) {
            preview.style.display = "block";
            preview.src = URL.createObjectURL(file);
        }
    });
});
