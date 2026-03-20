document.addEventListener('DOMContentLoaded', function() {
    const expiryTypeSelect = document.getElementById('id_expiry_type');
    const expiryDateLabel = document.getElementById('id_expiry_date_label');

    if (!expiryTypeSelect || !expiryDateLabel) {
        return;
    }

    const updateExpiryLabel = function() {
        expiryDateLabel.textContent = expiryTypeSelect.value === 'UB' ? 'Use By Date' : 'Best Before Date';
    };

    updateExpiryLabel();
    expiryTypeSelect.addEventListener('change', updateExpiryLabel);
});
