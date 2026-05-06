# from django import forms
# from .models import Recipe, FarmStory, RecipeProduct
# from products.models import Product

# class RecipeForm(forms.ModelForm):
#     ingredients_text = forms.CharField(
#         widget=forms.Textarea(attrs={
#             "rows": 4,
#             "class": "form-control",
#             "placeholder": "One ingredient per line"
#         }),
#         required=False,
#         label="Ingredients"
#     )

#     instructions_text = forms.CharField(
#         widget=forms.Textarea(attrs={
#             "rows": 6,
#             "class": "form-control",
#             "placeholder": "One step per line"
#         }),
#         required=False,
#         label="Instructions"
#     )

#     linked_products = forms.ModelMultipleChoiceField(
#         queryset=Product.objects.none(),
#         widget=forms.CheckboxSelectMultiple,
#         required=False,
#         label="Link products"
#     )

#     class Meta:
#         model = Recipe
#         fields = [
#             "title",
#             "description",
#             "seasonal_tag",
#             "image",
#             "status",
#             "ingredients_text",
#             "instructions_text",
#             "linked_products",
#         ]
#         widgets = {
#             "title": forms.TextInput(attrs={"class": "form-control"}),
#             "description": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
#             "seasonal_tag": forms.Select(attrs={"class": "form-select"}),
#             "image": forms.ClearableFileInput(attrs={"class": "form-control", "id": "imageInput"}),
#             "status": forms.Select(attrs={"class": "form-select"}),
#         }

#     def __init__(self, *args, **kwargs):
#         producer = kwargs.pop("producer", None)
#         super().__init__(*args, **kwargs)

#         # Load producer products
#         if producer:
#             print(Product.objects.filter(
#                 producer=producer,
#                 status=Product.Status.PUBLISHED
#             ))
#             self.fields["linked_products"].queryset = Product.objects.filter(
#                 producer=producer,
#                 status=Product.Status.PUBLISHED
#             )

#         # Load existing data when editing
#         if self.instance and self.instance.pk:
#             # Load ingredients list → textarea
#             self.fields["ingredients_text"].initial = "\n".join(self.instance.ingredients or [])

#             # Load instructions list → textarea
#             self.fields["instructions_text"].initial = "\n".join(self.instance.instructions or [])

#             # Pre-select linked products
#             self.fields["linked_products"].initial = Product.objects.filter(
#                 product_recipes__recipe=self.instance
#             ).values_list("id", flat=True)

#     def save(self, commit=True):
#         recipe = super().save(commit=False)

#         # Convert textarea → list
#         ingredients_raw = self.cleaned_data.get("ingredients_text", "")
#         instructions_raw = self.cleaned_data.get("instructions_text", "")

#         recipe.ingredients = [
#             line.strip() for line in ingredients_raw.splitlines() if line.strip()
#         ]
#         recipe.instructions = [
#             line.strip() for line in instructions_raw.splitlines() if line.strip()
#         ]

#         if commit:
#             recipe.save()

#             # Update linked products
#             RecipeProduct.objects.filter(recipe=recipe).delete()
#             for product in self.cleaned_data.get("linked_products", []):
#                 RecipeProduct.objects.create(recipe=recipe, product=product)

#         return recipe

# class FarmStoryForm(forms.ModelForm):
#     class Meta:
#         model = FarmStory
#         fields = ["title", "body", "image", "status"]

from django import forms
from .models import Recipe, FarmStory, RecipeProduct
from products.models import Product


class RecipeForm(forms.ModelForm):
    ingredients_text = forms.CharField(
        widget=forms.Textarea(attrs={
            "rows": 4,
            "class": "form-control",
            "placeholder": "One ingredient per line",
        }),
        required=True,
        label="Ingredients",
    )

    instructions_text = forms.CharField(
        widget=forms.Textarea(attrs={
            "rows": 6,
            "class": "form-control",
            "placeholder": "One step per line",
        }),
        required=True,
        label="Instructions",
    )

    linked_products = forms.ModelMultipleChoiceField(
        queryset=Product.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Link products",
    )

    class Meta:
        model = Recipe
        fields = [
            "title",
            "description",
            "seasonal_tag",
            "image",
            "ingredients_text",
            "instructions_text",
            "linked_products",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "seasonal_tag": forms.Select(attrs={"class": "form-select"}),
            "image": forms.ClearableFileInput(attrs={
                "class": "form-control",
                "id": "imageInput",
            }),
        }

    def __init__(self, *args, **kwargs):
        producer = kwargs.pop("producer", None)
        super().__init__(*args, **kwargs)

        if producer:
            self.fields["linked_products"].queryset = Product.objects.filter(
                producer=producer,
                status=Product.Status.PUBLISHED,
            )

        if self.instance and self.instance.pk:
            self.fields["ingredients_text"].initial = "\n".join(
                self.instance.ingredients or []
            )
            self.fields["instructions_text"].initial = "\n".join(
                self.instance.instructions or []
            )
            self.fields["linked_products"].initial = Product.objects.filter(
                product_recipes__recipe=self.instance
            )

    def clean(self):
        cleaned = super().clean()

        ingredients_text = cleaned.get("ingredients_text", "").strip()
        instructions_text = cleaned.get("instructions_text", "").strip()

        if not ingredients_text:
            self.add_error("ingredients_text", "At least one ingredient is required.")

        if not instructions_text:
            self.add_error("instructions_text", "At least one instruction step is required.")

        return cleaned

    def save(self, commit=True):
        recipe = super().save(commit=False)

        ingredients_raw = self.cleaned_data.get("ingredients_text", "")
        instructions_raw = self.cleaned_data.get("instructions_text", "")

        recipe.ingredients = [
            line.strip() for line in ingredients_raw.splitlines() if line.strip()
        ]
        recipe.instructions = [
            line.strip() for line in instructions_raw.splitlines() if line.strip()
        ]

        if commit:
            recipe.save()
            RecipeProduct.objects.filter(recipe=recipe).delete()

            for product in self.cleaned_data.get("linked_products", []):
                RecipeProduct.objects.create(recipe=recipe, product=product)

        return recipe


class FarmStoryForm(forms.ModelForm):
    class Meta:
        model = FarmStory
        fields = ["title", "body", "image", "status"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "body": forms.Textarea(attrs={"class": "form-control", "rows": 8}),
            "image": forms.ClearableFileInput(attrs={
                "class": "form-control",
                "id": "imageInput",
            }),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def clean_body(self):
        body = self.cleaned_data.get("body", "").strip()

        if len(body) < 50:
            raise forms.ValidationError("Farm story must be at least 50 characters long.")

        return body