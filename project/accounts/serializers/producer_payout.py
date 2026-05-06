from rest_framework import serializers
from accounts.models import Producer
import re

class ProducerPayoutSerializer(serializers.ModelSerializer):

    class Meta:
        model = Producer
        fields = [
            "payout_method",
            "bank_account_name",
            "bank_sort_code",
            "bank_account_number",
            "paypal_email",
            "cheque_payee_name",
            "cheque_postal_address",
            # "cheque_address_line1",
            # "cheque_address_line2",
            # "cheque_city",
            # "cheque_postcode",
        ]

    def validate(self, data):
        method = data.get("payout_method", self.instance.payout_method)

        # -----------------------------
        # BANK TRANSFER VALIDATION
        # -----------------------------
        if method == "BT":
            name = data.get("bank_account_name") or self.instance.bank_account_name
            sort_code = data.get("bank_sort_code") or self.instance.bank_sort_code
            account_number = data.get("bank_account_number") or self.instance.bank_account_number

            # Name
            if not name or not name.strip():
                raise serializers.ValidationError({"bank_account_name": "Bank account name is required."})
            if name.strip().lower() == "none":
                raise serializers.ValidationError({"bank_account_name": "Bank account name cannot be 'None'."})

            # Sort code
            if not sort_code:
                raise serializers.ValidationError({"bank_sort_code": "Sort code is required."})
            cleaned = sort_code.replace("-", "")
            if not cleaned.isdigit() or len(cleaned) != 6:
                raise serializers.ValidationError({"bank_sort_code": "Sort code must be 6 digits."})

            # Account number
            if not account_number:
                raise serializers.ValidationError({"bank_account_number": "Account number is required."})
            if not re.fullmatch(r"\d{8}", account_number):
                raise serializers.ValidationError({"bank_account_number": "Account number must be 8 digits."})

        # -----------------------------
        # PAYPAL VALIDATION
        # -----------------------------
        if method == "PP":
            email = data.get("paypal_email") or self.instance.paypal_email
            if not email:
                raise serializers.ValidationError({"paypal_email": "PayPal email is required."})
            if not re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email):
                raise serializers.ValidationError({"paypal_email": "Enter a valid PayPal email address."})

        # -----------------------------
        # CHEQUE VALIDATION
        # -----------------------------
        # if method == "CHQ":
        #     payee = data.get("cheque_payee_name") or self.instance.cheque_payee_name
        #     line1 = data.get("cheque_address_line1") or self.instance.cheque_address_line1
        #     city = data.get("cheque_city") or self.instance.cheque_city
        #     postcode = data.get("cheque_postcode") or self.instance.cheque_postcode

        #     if not payee:
        #         raise serializers.ValidationError({"cheque_payee_name": "Cheque payee name is required."})
        #     if not line1:
        #         raise serializers.ValidationError({"cheque_address_line1": "Address line 1 is required."})
        #     if not city:
        #         raise serializers.ValidationError({"cheque_city": "City is required."})
        #     if not postcode:
        #         raise serializers.ValidationError({"cheque_postcode": "Postcode is required."})

        #     postcode_regex = r"^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$"
        #     if not re.match(postcode_regex, postcode.upper()):
        #         raise serializers.ValidationError({"cheque_postcode": "Enter a valid UK postcode."})

        return data
