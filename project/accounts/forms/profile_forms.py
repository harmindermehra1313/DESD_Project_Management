import re

from django import forms
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError

from ..models import Address

UK_PHONE_RE = re.compile(
    r"^\+44(7\d{9}|1\d{9}|2\d{9}|3\d{9}|55\d{8}|56\d{8}|800\d{6}|808\d{6})$"
)

UK_POSTCODE_RE = re.compile(
    r"^("
    r"[Gg][Ii][Rr]\s?0[Aa]{2}|"
    r"(?!.*[CIKMOVcikmov])[A-Za-z]{1,2}[0-9][0-9A-Za-z]?\s?[0-9][A-Za-z]{2}"
    r")$"
)

NAME_RE = re.compile(r"^[A-Za-z]+(?:\s+[A-Za-z]+)+$")
ADDRESS_LINE_1_RE = re.compile(r"^[A-Za-z0-9\s,'./-]{5,}$")
ADDRESS_LINE_2_RE = re.compile(r"^[A-Za-z0-9\s,'./-]{2,}$")
CITY_RE = re.compile(r"^[A-Za-z\s'-]{2,}$")


def normalise_uk_phone(value):
    """
    Convert common UK phone formats into +44 format.

    Examples:
    - 07123456789    -> +447123456789
    - 01234567890    -> +441234567890
    - 02071234567    -> +442071234567
    - 00447123456789 -> +447123456789
    """

    value = (value or "").strip()
    value = re.sub(r"[\s\-()]", "", value)

    if value.startswith("0044"):
        value = "+44" + value[4:]

    if value.startswith(("07", "01", "02", "03", "08")):
        value = "+44" + value[1:]

    if value.startswith("+440"):
        value = "+44" + value[4:]

    return value


def normalise_uk_postcode(value):
    """
    Convert a UK postcode into uppercase outward/inward format.

    Example:
    - bs15tr -> BS1 5TR
    """

    value = (value or "").strip().upper()
    value = re.sub(r"\s+", "", value)

    if len(value) > 3:
        value = f"{value[:-3]} {value[-3:]}"

    return value


def title_case_name(value):
    """
    Return a simple title-cased name while preserving spacing normalisation.
    """

    return " ".join(word.capitalize() for word in value.split())


class AccountDetailsForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        label="Full name",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter full name",
                "autocomplete": "name",
            }
        ),
    )

    phone = forms.CharField(
        max_length=20,
        label="Phone number",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "+447123456789",
                "autocomplete": "tel",
                "inputmode": "tel",
            }
        ),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        if user:
            self.fields["name"].initial = user.name
            self.fields["phone"].initial = user.phone

    def clean_name(self):
        name = self.cleaned_data["name"].strip()

        if re.search(r"\d", name):
            raise ValidationError("Name cannot contain numbers.")

        if not NAME_RE.match(name):
            raise ValidationError("Enter your full name using letters and spaces only.")

        return title_case_name(name)

    def clean_phone(self):
        phone = normalise_uk_phone(self.cleaned_data["phone"])

        if not UK_PHONE_RE.match(phone):
            raise ValidationError(
                "Enter a valid UK phone number, for example +447123456789."
            )

        return phone

    def save(self):
        self.user.name = self.cleaned_data["name"]
        self.user.phone = self.cleaned_data["phone"]
        self.user.save(update_fields=["name", "phone"])

        producer = getattr(self.user, "producer_profile", None)

        if producer:
            producer.contact_phone = self.cleaned_data["phone"]
            producer.save(update_fields=["contact_phone"])

        return self.user


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = [
            "line1",
            "line2",
            "city",
            "postcode",
        ]

        widgets = {
            "line1": forms.TextInput(
                attrs={
                    "id": "line1",
                    "class": "form-control",
                    "placeholder": "Address line 1",
                    "autocomplete": "address-line1",
                }
            ),
            "line2": forms.TextInput(
                attrs={
                    "id": "line2",
                    "class": "form-control",
                    "placeholder": "Address line 2",
                    "autocomplete": "address-line2",
                }
            ),
            "city": forms.TextInput(
                attrs={
                    "id": "city",
                    "class": "form-control",
                    "placeholder": "City",
                    "autocomplete": "address-level2",
                }
            ),
            "postcode": forms.TextInput(
                attrs={
                    "id": "postcode",
                    "class": "form-control",
                    "placeholder": "Postcode",
                    "autocomplete": "postal-code",
                }
            ),
        }

    def clean_line1(self):
        line1 = self.cleaned_data["line1"].strip()

        if not ADDRESS_LINE_1_RE.match(line1):
            raise ValidationError(
                "Enter a valid address line using letters, numbers, spaces and common address punctuation."
            )

        if not re.search(r"[A-Za-z]{2,}", line1):
            raise ValidationError(
                "Address line 1 must include a street, building, or property name."
            )

        return line1

    def clean_line2(self):
        line2 = self.cleaned_data.get("line2", "")

        if not line2:
            return line2

        line2 = line2.strip()

        if not ADDRESS_LINE_2_RE.match(line2):
            raise ValidationError(
                "Address line 2 can only contain letters, numbers, spaces and common address punctuation."
            )

        return line2

    def clean_city(self):
        city = self.cleaned_data["city"].strip()

        if not CITY_RE.match(city):
            raise ValidationError(
                "Enter a valid UK town or city using letters, spaces, hyphens, or apostrophes."
            )

        return city

    def clean_postcode(self):
        postcode = normalise_uk_postcode(self.cleaned_data["postcode"])

        if not UK_POSTCODE_RE.match(postcode):
            raise ValidationError("Enter a valid UK postcode, for example BS1 5TR.")

        return postcode


class ProfilePasswordChangeForm(forms.Form):
    current_password = forms.CharField(
        label="Current password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter current password",
                "autocomplete": "current-password",
            }
        ),
    )

    new_password = forms.CharField(
        label="New password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter new password",
                "autocomplete": "new-password",
            }
        ),
    )

    confirm_password = forms.CharField(
        label="Confirm new password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Confirm new password",
                "autocomplete": "new-password",
            }
        ),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_current_password(self):
        current_password = self.cleaned_data["current_password"]

        if not self.user.check_password(current_password):
            raise ValidationError("The current password is incorrect.")

        return current_password

    def clean(self):
        cleaned_data = super().clean()

        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        if new_password and confirm_password and new_password != confirm_password:
            raise ValidationError("The new password fields do not match.")

        if new_password:
            password_validation.validate_password(new_password, self.user)

        return cleaned_data

    def save(self):
        self.user.set_password(self.cleaned_data["new_password"])
        self.user.save(update_fields=["password"])

        return self.user
