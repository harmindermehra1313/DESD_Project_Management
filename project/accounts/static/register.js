document.addEventListener('DOMContentLoaded', function () {

  // Role buttons
  const btnCustomer = document.getElementById('btnCustomer');
  const btnProducer = document.getElementById('btnProducer');
  const roleInput = document.getElementById('roleInput');

  const customerSection = document.getElementById('customerSection');
  const producerSection = document.getElementById('producerSection');
  const accountTypeSelect = document.getElementById('customer_account_type');

  // nested containers
  const customerBusinessFields = document.getElementById('customerBusinessFields');
  const customerCommunityFields = document.getElementById('customerCommunityFields');

  // producer payout fields
  const bankFields = document.getElementById('bankFields');
  const paypalFields = document.getElementById('paypalFields');

  // password match
  const password = document.getElementById('password');
  const confirm = document.getElementById('confirm_password');
  const passwordMatch = document.getElementById('passwordMatch');

  // helpers
  function showElement(el) { if (!el) return; el.classList.remove('visually-hidden'); el.hidden = false; enableInputs(el, true); }
  function hideElement(el) { if (!el) return; el.classList.add('visually-hidden'); el.hidden = true; enableInputs(el, false); }
  function enableInputs(container, enable) {
    if (!container) return;
    container.querySelectorAll('input, textarea, select').forEach(i => i.disabled = !enable);
  }

  // set role view
  function setRole(role) {
    roleInput.value = role;
    if (role === 'producer') {
      showElement(producerSection);
      hideElement(customerSection);
      btnProducer.classList.add('active');
      btnCustomer.classList.remove('active');
      hideElement(document.getElementById('accountTypeWrapper'));
    } else {
      showElement(customerSection);
      hideElement(producerSection);
      btnCustomer.classList.add('active');
      btnProducer.classList.remove('active');
      showElement(document.getElementById('accountTypeWrapper'));
    }
  }

  // initialize role from hidden input or default
  setRole(roleInput.value || 'customer');

  btnCustomer.addEventListener('click', () => setRole('customer'));
  btnProducer.addEventListener('click', () => setRole('producer'));

  // account type change: show/hide fields depending on selection and set hidden organisation_type
  const orgTypeInput = document.getElementById('organisation_type');
  function onAccountTypeChange() {
    const val = accountTypeSelect.value;
    // hide all extras first
    hideElement(customerBusinessFields);
    hideElement(customerCommunityFields);

    if (val === 'INDIVIDUAL') {
      orgTypeInput.value = 'Individual';
    } else if (val === 'BUSINESS') {
      orgTypeInput.value = 'Business';
      showElement(customerBusinessFields);
    } else if (val === 'COMMUNITY_GROUP') {
      orgTypeInput.value = 'Community Group';
      showElement(customerCommunityFields);
    }
  }

  accountTypeSelect.addEventListener('change', onAccountTypeChange);
  onAccountTypeChange(); // initialize

  // Producer payout method toggle
  function updatePayoutFields() {
    const method = document.querySelector('input[name="payout_method"]:checked')?.value || 'BANK_TRANSFER';
    if (method === 'BANK_TRANSFER') {
      showElement(bankFields);
      hideElement(paypalFields);
    } else if (method === 'PAYPAL') {
      hideElement(bankFields);
      showElement(paypalFields);
    } else {
      hideElement(bankFields);
      hideElement(paypalFields);
    }
  }
  document.querySelectorAll('input[name="payout_method"]').forEach(r => r.addEventListener('change', updatePayoutFields));
  updatePayoutFields();

  // Password match feedback
  function checkPasswordMatch() {
    if (!password.value && !confirm.value) { passwordMatch.textContent = ''; return; }
    if (password.value === confirm.value) {
      passwordMatch.textContent = 'Passwords match';
      passwordMatch.style.color = 'green';
    } else {
      passwordMatch.textContent = 'Passwords do not match';
      passwordMatch.style.color = 'red';
    }
  }
  password.addEventListener('input', checkPasswordMatch);
  confirm.addEventListener('input', checkPasswordMatch);

  // Client-side submit validation
  const form = document.getElementById('registerForm');
  form.addEventListener('submit', function (e) {
    // Basic HTML5 validity
    if (!form.checkValidity()) {
      e.preventDefault();
      form.reportValidity();
      return;
    }
    // Password match
    if (password.value !== confirm.value) {
      e.preventDefault();
      confirm.focus();
      passwordMatch.textContent = 'Passwords do not match';
      passwordMatch.style.color = 'red';
      return;
    }
    // Disable hidden nested fields so server ignores them
    document.querySelectorAll('.nested-fields').forEach(container => {
      const hidden = container.classList.contains('visually-hidden') || container.hidden;
      container.querySelectorAll('input, textarea, select').forEach(el => el.disabled = hidden);
    });
  });

});