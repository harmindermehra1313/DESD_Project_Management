document.addEventListener("DOMContentLoaded", () => {
 
  const accountForm = document
    .querySelector('form input[name="form_type"][value="account"]')
    ?.closest("form");

  const addressForm = document
    .querySelector('form input[name="form_type"][value="address"]')
    ?.closest("form");

  const passwordForm = document
    .querySelector('form input[name="form_type"][value="password"]')
    ?.closest("form");

  const fullName = document.querySelector('[name="name"]');
  const phone = document.querySelector('[name="phone"]');

  const line1 = document.querySelector('[name="line1"]');
  const line2 = document.querySelector('[name="line2"]');
  const city = document.querySelector('[name="city"]');
  const postcode = document.querySelector('[name="postcode"]');

  const currentPassword = document.querySelector('[name="current_password"]');
  const newPassword = document.querySelector('[name="new_password"]');
  const confirmPassword = document.querySelector('[name="confirm_password"]');

  function getFieldWrapper(input) {
    return input.closest(".profile-field-wrapper") || input.parentElement;
  }

  function clearFieldError(input) {
    if (!input) return;

    const wrapper = getFieldWrapper(input);
    const existing = wrapper.querySelector(".field-error-message");

    if (existing) {
      existing.remove();
    }

    input.classList.remove("is-invalid");
  }

  function showFieldError(input, message) {
    if (!input) return;

    clearFieldError(input);

    const wrapper = getFieldWrapper(input);
    const div = document.createElement("div");

    div.className = "field-error-message text-danger fw-bold small mt-1";
    div.textContent = message;

    wrapper.appendChild(div);

    input.classList.remove("is-valid");
    input.classList.add("is-invalid");
  }

  function showFieldSuccess(input) {
    if (!input) return;

    clearFieldError(input);

    input.classList.remove("is-invalid");
    input.classList.add("is-valid");
  }

  function clearFieldState(input) {
    if (!input) return;

    clearFieldError(input);

    input.classList.remove("is-invalid");
    input.classList.remove("is-valid");
  }

  function titleCaseName(input) {
    if (!input) return;

    const value = input.value;

    if (value.endsWith(" ")) {
      return;
    }

    input.value = value
      .split(" ")
      .map((word) => {
        if (!word) return "";
        return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
      })
      .join(" ");
  }

  function getUKPhoneMaxLength(value) {
    if (value.startsWith("+44800") || value.startsWith("+44808")) {
      return 12;
    }

    if (
      value.startsWith("+447") ||
      value.startsWith("+441") ||
      value.startsWith("+442") ||
      value.startsWith("+443") ||
      value.startsWith("+4455") ||
      value.startsWith("+4456")
    ) {
      return 13;
    }

    return 13;
  }

  function normaliseUKPhone(input) {
    if (!input) return;

    let value = input.value.trim();

    // Remove spaces, brackets and hyphens.
    value = value.replace(/[\s\-()]/g, "");

    // Convert 0044 format to +44.
    if (value.startsWith("0044")) {
      value = "+44" + value.substring(4);
    }

    // Convert UK mobile format: 07123456789 → +447123456789.
    if (value.startsWith("07")) {
      value = "+44" + value.substring(1);
    }

    // Convert common UK landline/non-geographic formats.
    if (
      value.startsWith("01") ||
      value.startsWith("02") ||
      value.startsWith("03") ||
      value.startsWith("08")
    ) {
      value = "+44" + value.substring(1);
    }

    // Fix accidental +440.
    if (value.startsWith("+440")) {
      value = "+44" + value.substring(4);
    }

    const maxLength = getUKPhoneMaxLength(value);

    if (value.length > maxLength) {
      value = value.substring(0, maxLength);
    }

    input.value = value;
  }

  function formatUKPostcode(input) {
    if (!input) return;

    let value = input.value.toUpperCase().replace(/\s+/g, "");

    if (value.length > 3) {
      value = value.slice(0, value.length - 3) + " " + value.slice(-3);
    }

    input.value = value;
  }

  

  function validateName() {
    if (!fullName) return true;

    const value = fullName.value.trim();

    if (!value) {
      showFieldError(fullName, "Enter your full name.");
      return false;
    }

    if (/\d/.test(value)) {
      showFieldError(fullName, "Name cannot contain numbers.");
      return false;
    }

    const namePattern = /^[A-Za-z]+(?:\s+[A-Za-z]+)+$/;

    if (!namePattern.test(value)) {
      showFieldError(
        fullName,
        "Enter your full name using letters and spaces only. Use first and last name.",
      );
      return false;
    }

    showFieldSuccess(fullName);
    return true;
  }

  if (fullName) {
    fullName.addEventListener("input", () => {
      titleCaseName(fullName);

      if (!fullName.value.trim()) {
        clearFieldState(fullName);
        return;
      }

      validateName();
    });

    fullName.addEventListener("blur", validateName);
  }

 

  function validatePhone() {
    if (!phone) return true;

    normaliseUKPhone(phone);

    const value = phone.value.trim();

    /*
      Allows:
      - +447123456789 mobile
      - +441234567890 landline
      - +442071234567 London-style landline
      - +443xxxxxxxxx non-geographic
      - +44800xxxxxxx / +44808xxxxxxx freephone-style
    */
    const ukPhonePattern =
      /^\+44(7\d{9}|1\d{9}|2\d{9}|3\d{9}|800\d{6}|808\d{6})$/;

    if (!value) {
      showFieldError(phone, "Enter a phone number.");
      return false;
    }

    if (!value.startsWith("+44")) {
      showFieldError(phone, "Enter a UK phone number starting with +44.");
      return false;
    }

    if (!ukPhonePattern.test(value)) {
      showFieldError(
        phone,
        "Enter a valid UK phone number, for example +447123456789 or +441234567890.",
      );
      return false;
    }

    showFieldSuccess(phone);
    return true;
  }

  if (phone) {
    phone.addEventListener("input", () => {
      normaliseUKPhone(phone);
      clearFieldState(phone);

      const value = phone.value.trim();
      const maxLength = getUKPhoneMaxLength(value);

      if (value.length === maxLength) {
        validatePhone();
      }
    });

    phone.addEventListener("blur", validatePhone);
  }



  function validateAddressLine1() {
    if (!line1) return true;

    const value = line1.value.trim();

    const addressPattern = /^[A-Za-z0-9\s,'./-]{5,}$/;
    const hasLetters = /[A-Za-z]{2,}/.test(value);

    if (!value) {
      showFieldError(line1, "Enter address line 1.");
      return false;
    }

    if (!addressPattern.test(value)) {
      showFieldError(
        line1,
        "Enter a valid address line using letters, numbers, spaces and common address punctuation.",
      );
      return false;
    }

    if (!hasLetters) {
      showFieldError(
        line1,
        "Address line 1 must include a street, building, or property name.",
      );
      return false;
    }

    showFieldSuccess(line1);
    return true;
  }

  function validateAddressLine2() {
    if (!line2) return true;

    const value = line2.value.trim();

    if (!value) {
      clearFieldState(line2);
      return true;
    }

    const addressLine2Pattern = /^[A-Za-z0-9\s,'./-]{2,}$/;

    if (!addressLine2Pattern.test(value)) {
      showFieldError(
        line2,
        "Address line 2 can only contain letters, numbers, spaces and common address punctuation.",
      );
      return false;
    }

    showFieldSuccess(line2);
    return true;
  }

  function validateCity() {
    if (!city) return true;

    const value = city.value.trim();

    /*
      Allows:
      - Bristol
      - Weston-super-Mare
      - King's Lynn
      - Stoke on Trent
    */
    const cityPattern = /^[A-Za-z\s'-]{2,}$/;

    if (!value) {
      showFieldError(city, "Enter a town or city.");
      return false;
    }

    if (!cityPattern.test(value)) {
      showFieldError(
        city,
        "Enter a valid UK town or city using letters, spaces, hyphens, or apostrophes.",
      );
      return false;
    }

    showFieldSuccess(city);
    return true;
  }

  async function validatePostcode() {
    if (!postcode) return true;

    formatUKPostcode(postcode);

    const value = postcode.value.trim();

    const ukPostcodeRegex =
      /^([Gg][Ii][Rr] 0[Aa]{2}|(?!.*[CIKMOV])[A-Za-z]{1,2}[0-9][0-9A-Za-z]?\s?[0-9][A-Za-z]{2})$/;

    if (!value) {
      showFieldError(postcode, "Enter a postcode.");
      return false;
    }

    if (!ukPostcodeRegex.test(value)) {
      showFieldError(
        postcode,
        "Enter a valid UK postcode format, for example BS1 5TR or B66 3EX.",
      );
      return false;
    }

    try {
      showFieldError(postcode, "Checking postcode...");

      const response = await fetch(
        `https://api.postcodes.io/postcodes/${encodeURIComponent(value)}`,
      );

      const data = await response.json();

      if (!response.ok || data.status !== 200 || !data.result) {
        showFieldError(
          postcode,
          "This postcode could not be found. Check the postcode and try again.",
        );
        return false;
      }

      postcode.value = data.result.postcode;

      showFieldSuccess(postcode);
      return true;
    } catch (error) {
      showFieldError(
        postcode,
        "Postcode validation is temporarily unavailable. Please try again.",
      );
      return false;
    }
  }

  if (line1) {
    line1.addEventListener("input", () => clearFieldState(line1));
    line1.addEventListener("blur", validateAddressLine1);
  }

  if (line2) {
    line2.addEventListener("input", () => clearFieldState(line2));
    line2.addEventListener("blur", validateAddressLine2);
  }

  if (city) {
    city.addEventListener("input", () => clearFieldState(city));
    city.addEventListener("blur", validateCity);
  }

  if (postcode) {
    postcode.addEventListener("input", () => {
      formatUKPostcode(postcode);
      clearFieldState(postcode);
    });

    postcode.addEventListener("blur", async () => {
      await validatePostcode();
    });
  }

 

  function validateCurrentPassword() {
    if (!currentPassword) return true;

    if (!currentPassword.value.trim()) {
      showFieldError(currentPassword, "Enter the current password.");
      return false;
    }

    showFieldSuccess(currentPassword);
    return true;
  }

  function validateNewPassword() {
    if (!newPassword) return true;

    const value = newPassword.value;
    const missing = [];

    if (!value) {
      showFieldError(newPassword, "Enter a new password.");
      return false;
    }

    if (value.length < 8) missing.push("8+ characters");
    if (!/[A-Z]/.test(value)) missing.push("1 uppercase letter");
    if (!/[a-z]/.test(value)) missing.push("1 lowercase letter");
    if (!/[0-9]/.test(value)) missing.push("1 number");
    if (!/[@$!%*?&]/.test(value)) missing.push("1 symbol (@$!%*?&)");

    if (missing.length > 0) {
      showFieldError(newPassword, "Missing: " + missing.join(", ") + ".");
      return false;
    }

    showFieldSuccess(newPassword);
    return true;
  }

  function validatePasswordMatch() {
    if (!newPassword || !confirmPassword) return true;

    if (!confirmPassword.value) {
      showFieldError(confirmPassword, "Confirm the new password.");
      return false;
    }

    if (newPassword.value !== confirmPassword.value) {
      showFieldError(confirmPassword, "Passwords do not match.");
      return false;
    }

    showFieldSuccess(confirmPassword);
    return true;
  }

  if (currentPassword) {
    currentPassword.addEventListener("input", () =>
      clearFieldState(currentPassword),
    );

    currentPassword.addEventListener("blur", validateCurrentPassword);
  }

  if (newPassword) {
    newPassword.addEventListener("input", () => {
      validateNewPassword();

      if (confirmPassword && confirmPassword.value) {
        validatePasswordMatch();
      }
    });

    newPassword.addEventListener("blur", validateNewPassword);
  }

  if (confirmPassword) {
    confirmPassword.addEventListener("input", validatePasswordMatch);
    confirmPassword.addEventListener("blur", validatePasswordMatch);
  }


  document.querySelectorAll("[data-password-toggle]").forEach((button) => {
    const targetId = button.dataset.target;
    const input = document.getElementById(targetId);
    const icon = button.querySelector("i");

    if (!input) {
      button.disabled = true;
      return;
    }

    button.addEventListener("click", () => {
      const passwordIsHidden = input.type === "password";

      input.type = passwordIsHidden ? "text" : "password";

      button.setAttribute(
        "aria-label",
        passwordIsHidden ? "Hide password" : "Show password",
      );

      if (icon) {
        icon.classList.toggle("bi-eye", !passwordIsHidden);
        icon.classList.toggle("bi-eye-slash", passwordIsHidden);
      }
    });
  });


  if (accountForm) {
    accountForm.addEventListener("submit", (event) => {
      const validName = validateName();
      const validPhone = validatePhone();

      if (!validName || !validPhone) {
        event.preventDefault();
      }
    });
  }

  if (addressForm) {
    addressForm.addEventListener("submit", async (event) => {
      event.preventDefault();

      const validLine1 = validateAddressLine1();
      const validLine2 = validateAddressLine2();
      const validCity = validateCity();
      const validPostcode = await validatePostcode();

      if (!validLine1 || !validLine2 || !validCity || !validPostcode) {
        return;
      }

      HTMLFormElement.prototype.submit.call(addressForm);
    });
  }

  if (passwordForm) {
    passwordForm.addEventListener("submit", (event) => {
      const validCurrentPassword = validateCurrentPassword();
      const validNewPassword = validateNewPassword();
      const validPasswordMatch = validatePasswordMatch();

      if (!validCurrentPassword || !validNewPassword || !validPasswordMatch) {
        event.preventDefault();
      }
    });
  }
});
