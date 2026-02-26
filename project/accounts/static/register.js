// document.addEventListener('DOMContentLoaded', function () {

//   // Role buttons
//   const btnCustomer = document.getElementById('btnCustomer');
//   const btnProducer = document.getElementById('btnProducer');
//   const roleInput = document.getElementById('roleInput');

//   const customerSection = document.getElementById('customerSection');
//   const producerSection = document.getElementById('producerSection');
//   const accountTypeSelect = document.getElementById('customer_account_type');

//   // nested containers
//   const customerBusinessFields = document.getElementById('customerBusinessFields');
//   const customerCommunityFields = document.getElementById('customerCommunityFields');

//   // producer payout fields
//   const bankFields = document.getElementById('bankFields');
//   const paypalFields = document.getElementById('paypalFields');
//   const chequeFields = document.getElementById('chequeFields');

//   // password match
//   const password = document.getElementById('password');
//   const confirm = document.getElementById('confirm_password');
//   const passwordMatch = document.getElementById('passwordMatch');

//   // helpers
//   function showElement(el) { if (!el) return; el.classList.remove('visually-hidden'); el.hidden = false; enableInputs(el, true); }
//   function hideElement(el) { if (!el) return; el.classList.add('visually-hidden'); el.hidden = true; enableInputs(el, false); }
//   function enableInputs(container, enable) {
//     if (!container) return;
//     container.querySelectorAll('input, textarea, select').forEach(i => i.disabled = !enable);
//   }

//   // set role view
//   function setRole(role) {
//     roleInput.value = role;
//     if (role === 'producer') {
//       showElement(producerSection);
//       hideElement(customerSection);
//       btnProducer.classList.add('active');
//       btnCustomer.classList.remove('active');
//       hideElement(document.getElementById('accountTypeWrapper'));
//     } else {
//       showElement(customerSection);
//       hideElement(producerSection);
//       btnCustomer.classList.add('active');
//       btnProducer.classList.remove('active');
//       showElement(document.getElementById('accountTypeWrapper'));
//     }
//   }

//   // initialize role from hidden input or default
//   setRole(roleInput.value || 'customer');

//   btnCustomer.addEventListener('click', () => setRole('customer'));
//   btnProducer.addEventListener('click', () => setRole('producer'));

//   // account type change: show/hide fields depending on selection and set hidden organisation_type
//   const orgTypeInput = document.getElementById('organisation_type');
//   function onAccountTypeChange() {
//     const val = accountTypeSelect.value;
//     // hide all extras first
//     hideElement(customerBusinessFields);
//     hideElement(customerCommunityFields);

//     if (val === 'INDIVIDUAL') {
//       orgTypeInput.value = 'Individual';
//     } else if (val === 'BUSINESS') {
//       orgTypeInput.value = 'Business';
//       showElement(customerBusinessFields);
//     } else if (val === 'COMMUNITY_GROUP') {
//       orgTypeInput.value = 'Community Group';
//       showElement(customerCommunityFields);
//     }
//   }

//   accountTypeSelect.addEventListener('change', onAccountTypeChange);
//   onAccountTypeChange(); // initialize

//   // Producer payout method toggle
//   function updatePayoutFields() {
//     const method = document.querySelector('input[name="payout_method"]:checked')?.value || 'BANK_TRANSFER';

//       if (method === 'BANK_TRANSFER') {
//         showElement(bankFields);
//         hideElement(paypalFields);
//         hideElement(chequeFields);
//       } else if (method === 'PAYPAL') {
//         hideElement(bankFields);
//         showElement(paypalFields);
//         hideElement(chequeFields);
//       } else if (method === 'CHEQUE') {
//         hideElement(bankFields);
//         hideElement(paypalFields);
//         showElement(chequeFields);
//       }
//   }
//   document.querySelectorAll('input[name="payout_method"]').forEach(r =>
//     r.addEventListener('change', updatePayoutFields)
//   );
//   updatePayoutFields();

//   // Password match feedback
//   function checkPasswordMatch() {
//     if (!password.value && !confirm.value) { passwordMatch.textContent = ''; return; }
//     if (password.value === confirm.value) {
//       passwordMatch.textContent = 'Passwords match';
//       passwordMatch.style.color = 'green';
//     } else {
//       passwordMatch.textContent = 'Passwords do not match';
//       passwordMatch.style.color = 'red';
//     }
//   }
//   password.addEventListener('input', checkPasswordMatch);
//   confirm.addEventListener('input', checkPasswordMatch);

//   // Client-side submit validation
//   const form = document.getElementById('registerForm');
//   form.addEventListener('submit', function (e) {
//     // Basic HTML5 validity
//     if (!form.checkValidity()) {
//       e.preventDefault();
//       form.reportValidity();
//       return;
//     }
//     // Password match
//     if (password.value !== confirm.value) {
//       e.preventDefault();
//       confirm.focus();
//       passwordMatch.textContent = 'Passwords do not match';
//       passwordMatch.style.color = 'red';
//       return;
//     }
//     // Disable hidden nested fields so server ignores them
//     document.querySelectorAll('.nested-fields').forEach(container => {
//       const hidden = container.classList.contains('visually-hidden') || container.hidden;
//       container.querySelectorAll('input, textarea, select').forEach(el => el.disabled = hidden);
//     });
//   });

// });

// form.addEventListener('submit', async function (e) {
//   e.preventDefault();

//   // HTML5 validation
//   if (!form.checkValidity()) {
//     form.reportValidity();
//     return;
//   }

//   // Password match
//   if (password.value !== confirm.value) {
//     passwordMatch.textContent = 'Passwords do not match';
//     passwordMatch.style.color = 'red';
//     confirm.focus();
//     return;
//   }

//   // Disable hidden nested fields
//   document.querySelectorAll('.nested-fields').forEach(container => {
//     const hidden = container.classList.contains('visually-hidden') || container.hidden;
//     container.querySelectorAll('input, textarea, select').forEach(el => el.disabled = hidden);
//   });

//   // Prepare form data
//   const formData = new FormData(form);

//   // Send to API
//   const response = await fetch('/api/register/', {
//     method: 'POST',
//     body: formData
//   });

//   const errorBox = document.getElementById('formErrors');

//   if (!response.ok) {
//     const data = await response.json();

//     // Build readable error message
//     let messages = [];
//     for (const field in data) {
//       messages.push(`${field}: ${data[field].join(', ')}`);
//     }

//     // Show pop-up
//     errorBox.textContent = messages.join(' | ');
//     errorBox.classList.remove('visually-hidden');

//     window.scrollTo({ top: 0, behavior: 'smooth' });
//     return;
//   }

//   // Success → redirect or show success message
//   window.location.href = '/register/success/';
// });
// ------------------------------------------------------------
// Registration Form Logic (Clean Version)
// Sections:
// 1. Role switching (Customer / Producer)
// 2. Customer account type switching (Individual / Business / Community)
// 3. Producer payout method switching (Bank / PayPal / Cheque)
// 4. Password match feedback
// 5. Custom field validation (Full name, Phone, etc.)
// 6. Form submission + API error popup
// ------------------------------------------------------------

document.addEventListener('DOMContentLoaded', function () {
  // ------------------------------------------------------------
  // SECTION 0 — Element references
  // ------------------------------------------------------------

  const form = document.getElementById('registerForm');

  // Role buttons
  const btnCustomer = document.getElementById('btnCustomer');
  const btnProducer = document.getElementById('btnProducer');
  const roleInput = document.getElementById('roleInput');

  // Sections
  const customerSection = document.getElementById('customerSection');
  const producerSection = document.getElementById('producerSection');
  const accountTypeWrapper = document.getElementById('accountTypeWrapper');

  // Customer account type
  const accountTypeSelect = document.getElementById('customer_account_type');
  const orgTypeInput = document.getElementById('organisation_type');
  const customerBusinessFields = document.getElementById('customerBusinessFields');
  const customerCommunityFields = document.getElementById('customerCommunityFields');

  // Producer payout fields
  const bankFields = document.getElementById('bankFields');
  const paypalFields = document.getElementById('paypalFields');
  const chequeFields = document.getElementById('chequeFields');

  // Password fields
  const password = document.getElementById('password');
  const confirm = document.getElementById('confirm_password');
  const passwordMatch = document.getElementById('passwordMatch');

  // Error popup (top alert)
  const errorBox = document.getElementById('formErrors');

  // Common fields for custom validation
  const fullName = document.getElementById('name');
  const phone = document.getElementById('phone');
  const postcode = document.getElementById('postcode');
  const line1 = document.getElementById('line1');
  const city = document.getElementById('city');
  const businessReg = document.getElementById('business_registration_number');
  const communityReg = document.getElementById('community_registration_number');

  const bankAccountNumber = document.getElementById('bank_account_number');
  const bankSortCode = document.getElementById('bank_sort_code');
  const farmPostcode = document.getElementById('farm_postcode');
  const contactPhone = document.getElementById('contact_phone');
  const organicCert = document.getElementById('organic_certification_number');
  const contactname = document.getElementById('business_contact_person')
  const contactname2 = document.getElementById('community_contact')

  // ------------------------------------------------------------
  // Helper functions — show/hide, errors, etc.
  // ------------------------------------------------------------

  function showElement(el) {
    if (!el) return;
    el.classList.remove('visually-hidden');
    el.hidden = false;
    enableInputs(el, true);
  }

  function hideElement(el) {
    if (!el) return;
    el.classList.add('visually-hidden');
    el.hidden = true;
    enableInputs(el, false);
  }

  function enableInputs(container, enable) {
    container.querySelectorAll('input, textarea, select')
      .forEach(i => i.disabled = !enable);
  }

  // Inline error helpers (Bootstrap-style text, created from JS)
  function clearFieldError(input) {
    if (!input) return;
    const existing = input.parentElement.querySelector('.field-error-message');
    if (existing) {
      existing.remove();
    }
  }

  function showFieldError(input, message) {
    if (!input) return;
    clearFieldError(input);
    const div = document.createElement('div');
    div.className = 'field-error-message text-danger fw-bold small mt-1';
    div.textContent = message;
    input.parentElement.appendChild(div);
  }

  function clearAllFieldErrors() {
    form.querySelectorAll('.field-error-message').forEach(el => el.remove());
  }

  function clearTopErrorBox() {
    if (!errorBox) return;
    errorBox.classList.add('visually-hidden');
    errorBox.innerHTML = '';
  }

  function showTopErrorBox(messages) {
    if (!errorBox) return;
    if (!messages || messages.length === 0) {
      clearTopErrorBox();
      return;
    }
    const listItems = messages.map(msg => `<li>${msg}</li>`).join('');
    errorBox.innerHTML = `
      <div class="alert alert-danger mb-2">
        <p class="mb-1 fw-bold">Please correct the following errors:</p>
        <ul class="mb-0">
          ${listItems}
        </ul>
      </div>
    `;
    errorBox.classList.remove('visually-hidden');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // ------------------------------------------------------------
  // SECTION 1 — Role switching
  // ------------------------------------------------------------

  function setRole(role) {
    roleInput.value = role;

    if (role === 'producer') {
      showElement(producerSection);
      hideElement(customerSection);
      hideElement(accountTypeWrapper);
      btnProducer.classList.add('active');
      btnCustomer.classList.remove('active');
    } else {
      showElement(customerSection);
      hideElement(producerSection);
      showElement(accountTypeWrapper);
      btnCustomer.classList.add('active');
      btnProducer.classList.remove('active');
    }
  }

  setRole(roleInput.value || 'customer');

  btnCustomer.addEventListener('click', () => setRole('customer'));
  btnProducer.addEventListener('click', () => setRole('producer'));

  // ------------------------------------------------------------
  // SECTION 2 — Customer account type switching
  // ------------------------------------------------------------

  function onAccountTypeChange() {
    const val = accountTypeSelect.value;

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
  onAccountTypeChange();

  // ------------------------------------------------------------
  // SECTION 3 — Producer payout method switching
  // ------------------------------------------------------------

  function updatePayoutFields() {
    const method = document.querySelector('input[name="payout_method"]:checked')?.value || 'BANK_TRANSFER';

    if (method === 'BANK_TRANSFER') {
      showElement(bankFields);
      hideElement(paypalFields);
      hideElement(chequeFields);
    } else if (method === 'PAYPAL') {
      hideElement(bankFields);
      showElement(paypalFields);
      hideElement(chequeFields);
    } else if (method === 'CHEQUE') {
      hideElement(bankFields);
      hideElement(paypalFields);
      showElement(chequeFields);
    }
  }

  document.querySelectorAll('input[name="payout_method"]').forEach(r =>
    r.addEventListener('change', updatePayoutFields)
  );
  updatePayoutFields();

  // ------------------------------------------------------------
  // SECTION 4 — Password match feedback
  // ------------------------------------------------------------

  function checkPasswordMatch() {
    if (!password.value && !confirm.value) {
      passwordMatch.textContent = '';
      return;
    }
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

  // ------------------------------------------------------------
  // SECTION 5 — Auto-format sort code (UK: 12-34-56)
  // ------------------------------------------------------------

  if (bankSortCode) {
    bankSortCode.addEventListener('input', function () {
      let digits = this.value.replace(/\D/g, '');
      digits = digits.substring(0, 6); // max 6 digits
      let formatted = '';
      for (let i = 0; i < digits.length; i++) {
        if (i > 0 && i % 2 === 0) {
          formatted += '-';
        }
        formatted += digits[i];
      }
      this.value = formatted;
    });
  }
  // Auto-capitalise first letter of customer name
  if (fullName) {
    fullName.addEventListener('input', () => {
        let value = fullName.value;

        // Allow typing spaces normally
        if (value.endsWith(' ')) {
            return;
        }

        // Title-case only completed words
        fullName.value = value
            .split(' ')
            .map(word => {
                if (word.length === 0) return '';
                return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
            })
            .join(' ');
    });
  }
  if (contactname) {
    contactname.addEventListener('input', () => {
        let value = contactname.value;

        // Allow typing spaces normally
        if (value.endsWith(' ')) {
            return;
        }

        // Title-case only completed words
        contactname.value = value
            .split(' ')
            .map(word => {
                if (word.length === 0) return '';
                return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
            })
            .join(' ');
    });
  }
  if (contactname2) {
    contactname2.addEventListener('input', () => {
        let value = contactname2.value;

        // Allow typing spaces normally
        if (value.endsWith(' ')) {
            return;
        }

        // Title-case only completed words
        contactname2.value = value
            .split(' ')
            .map(word => {
                if (word.length === 0) return '';
                return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
            })
            .join(' ');
    });
  }
  // Auto-uppercase postcode fields
  function autoUppercase(input) {
      if (!input) return;
      input.addEventListener('input', () => {
          input.value = input.value.toUpperCase();
      });
  }

  autoUppercase(postcode);
  autoUppercase(farm_postcode);
  
  function normaliseUKPhone(input) {
    if (!input) return;

    input.addEventListener('input', () => {
        let v = input.value.replace(/\s+/g, ''); // remove spaces

        // If starts with 07 → convert to +44
        if (v.startsWith('07') && v.length >= 3) {
            v = '+44' + v.substring(1); // remove leading 0
        }

        // If starts with +440 → convert to +44
        if (v.startsWith('+440')) {
            v = '+44' + v.substring(4);
        }

        input.value = v;
    });
}

normaliseUKPhone(contact_phone);
normaliseUKPhone(phone); // customer phone if needed

  // ------------------------------------------------------------
  // SECTION 6 — Custom field validation (messages from JS)
  // ------------------------------------------------------------

  // Helper: attach simple custom message behaviour
  function addPatternMessage(input, message) {
    if (!input) return;
    input.addEventListener('invalid', function () {
      if (input.validity.valueMissing || input.validity.patternMismatch) {
        input.setCustomValidity(message);
      }
    });
    input.addEventListener('input', function () {
      input.setCustomValidity('');
      clearFieldError(input);
    });
  }

  // Full name: letters + spaces only, at least 2 words
  if (fullName) {
    addPatternMessage(fullName, 'Enter your full name using letters and spaces only (at least first and last name).');
  }

  // Phone: +44 followed by exactly 10 digits
  if (phone) {
    addPatternMessage(phone, 'Phone must be in the format +44XXXXXXXXXX (10 digits after +44).');
  }

  // Address line 1
  if (line1) {
    addPatternMessage(line1, 'Enter a valid address line (e.g., 123 High Street).');
  }

  // City
  if (city) {
    addPatternMessage(city, 'Enter a valid city name using letters, spaces, or hyphens.');
  }

  // Postcode (primary address)
  if (postcode) {
    addPatternMessage(postcode, 'Enter a valid UK postcode (e.g., B66 3EX).');
  }

  // Business registration number
  if (businessReg) {
    addPatternMessage(businessReg, 'Enter a valid UK Companies House registration number.');
  }

  // Community / charity registration number
  if (communityReg) {
    addPatternMessage(communityReg, 'Enter a valid UK charity or community registration number.');
  }

  // Farm postcode
  if (farmPostcode) {
    addPatternMessage(farmPostcode, 'Enter a valid UK postcode for the farm (e.g., B66 3EX).');
  }

  // Contact phone (producer)
  if (contactPhone) {
    addPatternMessage(contactPhone, 'Enter a valid UK phone number in the format +44XXXXXXXXXX.');
  }

  // Organic certification number
  if (organicCert) {
    addPatternMessage(organicCert, 'Enter a valid organic certification number (2–15 characters, letters, numbers, hyphens, or slashes).');
  }

  // Bank account number: exactly 8 digits
  if (bankAccountNumber) {
    addPatternMessage(bankAccountNumber, 'Bank account number must be exactly 8 digits.');
  }

  // Bank sort code: 12-34-56
  if (bankSortCode) {
    addPatternMessage(bankSortCode, 'Sort code must be in the format 12-34-56.');
  }

  // ------------------------------------------------------------
  // SECTION 7 — Form submission + validation + API error popup
  // ------------------------------------------------------------

  form.addEventListener('submit', async function (e) {
    e.preventDefault();

    clearAllFieldErrors();
    clearTopErrorBox();

    // HTML5 validation first
    if (!form.checkValidity()) {
      form.reportValidity();
    }

    const errorMessages = [];

    // Password match
    if (password.value !== confirm.value) {
      const msg = 'Passwords do not match.';
      passwordMatch.textContent = msg;
      passwordMatch.style.color = 'red';
      showFieldError(confirm, msg);
      errorMessages.push(msg);
    }

    // Full name pattern (letters + spaces, at least 2 words)
    if (fullName && fullName.value.trim()) {
      const namePattern = /^[A-Za-z]+(?:\s+[A-Za-z]+)+$/;
      if (!namePattern.test(fullName.value.trim())) {
        const msg = 'Full name must contain only letters and spaces, with at least first and last name.';
        showFieldError(fullName, msg);
        errorMessages.push(msg);
      }
    }

    // Bank account number: exactly 8 digits
    if (bankAccountNumber && !bankAccountNumber.disabled && bankAccountNumber.value.trim()) {
      const accPattern = /^\d{8}$/;
      if (!accPattern.test(bankAccountNumber.value.trim())) {
        const msg = 'Bank account number must be exactly 8 digits.';
        showFieldError(bankAccountNumber, msg);
        errorMessages.push(msg);
      }
    }

    // Sort code: 12-34-56
    if (bankSortCode && !bankSortCode.disabled && bankSortCode.value.trim()) {
      const sortPattern = /^\d{2}-\d{2}-\d{2}$/;
      if (!sortPattern.test(bankSortCode.value.trim())) {
        const msg = 'Sort code must be in the format 12-34-56.';
        showFieldError(bankSortCode, msg);
        errorMessages.push(msg);
      }
    }

    // Primary postcode (if present)
    if (postcode && postcode.value.trim() === '') {
      const msg = 'Enter your primary address postcode.';
      showFieldError(postcode, msg);
      errorMessages.push(msg);
    }

    // If any JS-level errors exist → stop and show top alert
    if (errorMessages.length > 0 || !form.checkValidity()) {
      if (errorMessages.length > 0) {
        showTopErrorBox(errorMessages);
      }
      return;
    }

    // Disable hidden nested fields so server ignores them
    document.querySelectorAll('.nested-fields').forEach(container => {
      const hidden = container.classList.contains('visually-hidden') || container.hidden;
      container.querySelectorAll('input, textarea, select').forEach(el => {
        el.disabled = hidden;
      });
    });

    // Prepare form data
    const formData = new FormData(form);

    // Send to API
    let response;
    try {
      response = await fetch('/accounts/api/register/', {
        method: 'POST',
        body: formData
      });
    } catch (err) {
      showTopErrorBox(['A network error occurred while submitting the form. Please try again.']);
      return;
    }

    // Handle API validation errors
    if (!response.ok) {
      let data;
      try {
        data = await response.json();
      } catch {
        showTopErrorBox(['An unexpected server error occurred. Please try again later.']);
        return;
      }

      const apiMessages = [];

      for (const field in data) {
        const messages = Array.isArray(data[field]) ? data[field] : [String(data[field])];
        const combined = messages.join(', ');
        apiMessages.push(`${field}: ${combined}`);

        // Inline error if field exists
        const input = form.querySelector(`[name="${field}"]`);
        if (input) {
          showFieldError(input, combined);
        }
      }

      if (apiMessages.length === 0) {
        apiMessages.push('There was a problem with your submission. Please check your details and try again.');
      }

      showTopErrorBox(apiMessages);
      return;
    }

    // Success → redirect
    window.location.href = '/accounts/login/?registered=1';
  });

});