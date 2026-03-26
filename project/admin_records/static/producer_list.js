function showProducerDetails(id) {
    const template = document.getElementById(`producer-template-${id}`);

    if (!template) {
        console.error("Producer template not found:", id);
        return;
    }

    const modalBody = document.getElementById("producerDetailsContent");
    modalBody.innerHTML = template.innerHTML;

    const modal = new bootstrap.Modal(document.getElementById("producerDetailsModal"));
    modal.show();
}