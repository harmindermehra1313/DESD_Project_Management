// freshness_check.js - Fresh ness checker UI logic

document.addEventListener('DOMContentLoaded', function() {
    const uploadArea = document.getElementById('uploadArea');
    const imageInput = document.getElementById('imageInput');
    const loadingState = document.getElementById('loadingState');
    const errorState = document.getElementById('errorState');
    const resultsSection = document.getElementById('resultsSection');

    // File input change handler
    imageInput.addEventListener('change', function() {
        if (this.files && this.files[0]) {
            handleImageUpload(this.files[0]);
        }
    });

    // Drag and drop handlers
    uploadArea.addEventListener('dragenter', preventDefaults, false);
    uploadArea.addEventListener('dragover', preventDefaults, false);
    uploadArea.addEventListener('dragleave', removeHighlight, false);
    uploadArea.addEventListener('drop', handleDrop, false);

    uploadArea.addEventListener('dragenter', addHighlight, false);
    uploadArea.addEventListener('dragover', addHighlight, false);

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    function addHighlight(e) {
        uploadArea.classList.add('drag-over');
    }

    function removeHighlight(e) {
        uploadArea.classList.remove('drag-over');
    }

    function handleDrop(e) {
        preventDefaults(e);
        removeHighlight(e);

        const dt = e.dataTransfer;
        const files = dt.files;

        if (files && files[0]) {
            handleImageUpload(files[0]);
        }
    }

    function handleImageUpload(file) {
        // Validate file
        const validTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/bmp', 'image/tiff', 'image/gif'];
        const maxSize = 10 * 1024 * 1024; // 10 MB

        if (!validTypes.includes(file.type)) {
            showError(`Unsupported file type '${file.type}'. Please upload a JPEG, PNG, or WebP image.`);
            return;
        }

        if (file.size > maxSize) {
            showError(`File size is ${(file.size / 1024 / 1024).toFixed(1)} MB. Maximum is 10 MB.`);
            return;
        }

        // Preview image
        const reader = new FileReader();
        reader.onload = function(e) {
            const previewImage = document.getElementById('previewImage');
            previewImage.src = e.target.result;
        };
        reader.readAsDataURL(file);

        // Submit to API
        analyzeImage(file);
    }

    function analyzeImage(file) {
        resultsSection.classList.add('d-none');
        errorState.classList.add('d-none');
        uploadArea.parentElement.classList.add('d-none');
        loadingState.classList.remove('d-none');

        const formData = new FormData();
        formData.append('image', file);

        fetch('/products/freshness/analyse/', {
            method: 'POST',
            body: formData,
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.error || 'Analysis failed');
                });
            }
            return response.json();
        })
        .then(data => {
            displayResults(data);
        })
        .catch(error => {
            showError(error.message || 'Failed to analyze image. Please try again.');
        })
        .finally(() => {
            loadingState.classList.add('d-none');
        });
    }

    function displayResults(data) {
        const { label, freshness_pct, scores, recommendation, explainability } = data;

        // Set result badge
        const resultBadge = document.getElementById('resultBadge');
        const badgeClass = label === 'Fresh' ? 'result-badge-fresh' 
                         : label === 'Borderline' ? 'result-badge-borderline' 
                         : 'result-badge-spoiled';
        resultBadge.textContent = label.toUpperCase();
        resultBadge.className = `badge rounded-pill p-4 mb-3 ${badgeClass}`;
        resultBadge.style.fontSize = '1.5rem';

        // Set result label and score
        document.getElementById('resultLabel').textContent = label + ' Produce';
        document.getElementById('freshnessScore').textContent = `Freshness: ${freshness_pct}%`;

        // Display scores
        const scoresContainer = document.getElementById('scoresContainer');
        scoresContainer.innerHTML = '';
        scores.forEach(score => {
            const scorePercentage = score.score;
            const scoreDiv = document.createElement('div');
            scoreDiv.className = 'col-md-4';
            scoreDiv.innerHTML = `
                <div class="score-card">
                    <div class="score-label">${score.label}</div>
                    <div class="score-value" style="color: ${score.colour};">${scorePercentage}%</div>
                    <div class="score-bar">
                        <div class="score-bar-fill" style="width: ${scorePercentage}%; background-color: ${score.colour};"></div>
                    </div>
                </div>
            `;
            scoresContainer.appendChild(scoreDiv);
        });

        // Display recommendation
        document.getElementById('recommendation').textContent = recommendation;

        // Display explainability images
        const explainabilityContainer = document.getElementById('explainabilityContainer');
        explainabilityContainer.innerHTML = '';

        const methods = ['grad_cam', 'integrated_gradients', 'lime', 'shap'];
        methods.forEach(method => {
            if (explainability[method]) {
                const { title, image } = explainability[method];
                const itemDiv = document.createElement('div');
                itemDiv.className = 'col-md-6';
                itemDiv.innerHTML = `
                    <div class="explainability-item">
                        <div class="explainability-title">${title}</div>
                        <img src="data:image/png;base64,${image}" alt="${title}" class="explainability-image">
                    </div>
                `;
                explainabilityContainer.appendChild(itemDiv);
            }
        });

        // Show results
        resultsSection.classList.remove('d-none');
    }

    function showError(message) {
        errorState.classList.remove('d-none');
        document.getElementById('errorMessage').textContent = message;
        uploadArea.parentElement.classList.remove('d-none');
        resultsSection.classList.add('d-none');
    }

    window.resetForm = function() {
        imageInput.value = '';
        uploadArea.classList.remove('drag-over');
        uploadArea.parentElement.classList.remove('d-none');
        resultsSection.classList.add('d-none');
        errorState.classList.add('d-none');
        loadingState.classList.add('d-none');
    };
});
