// Initialize Choices.js for allergen multi-select
if (typeof Choices !== 'undefined') {
    document.addEventListener('DOMContentLoaded', function() {
        const allergenSelect = document.getElementById('id_allergen');
        if (allergenSelect) {
            new Choices(allergenSelect, {
                removeItemButton: true,
                placeholder: true,
                placeholderValue: 'Select all that apply. Leave blank if none.',
                searchEnabled: true,
                shouldSort: false,
                silent: false
            });
        }
    });
} else {
    console.warn('Choices.js library not loaded');
}
