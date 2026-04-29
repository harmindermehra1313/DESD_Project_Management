import re

from products.models import Category, ProductType


PRODUCT_TYPE_RULES = {
    Category.FoodGroups.FRUIT: {
        "Apple": [
            "apple",
            "apples",
            "gala",
            "braeburn",
            "bramley",
            "cox",
            "granny smith",
            "pink lady",
        ],
        "Pear": ["pear", "pears"],
        "Strawberry": ["strawberry", "strawberries"],
        "Raspberry": ["raspberry", "raspberries"],
        "Blueberry": ["blueberry", "blueberries"],
        "Blackberry": ["blackberry", "blackberries"],
        "Plum": ["plum", "plums"],
        "Cherry": ["cherry", "cherries"],
    },
    Category.FoodGroups.VEGETABLES: {
        "Potato": ["potato", "potatoes", "maris piper", "king edward"],
        "Carrot": ["carrot", "carrots"],
        "Onion": ["onion", "onions", "spring onion", "red onion"],
        "Tomato": ["tomato", "tomatoes"],
        "Cabbage": ["cabbage"],
        "Lettuce": ["lettuce"],
        "Broccoli": ["broccoli"],
        "Cauliflower": ["cauliflower"],
        "Spinach": ["spinach"],
        "Kale": ["kale"],
        "Leek": ["leek", "leeks"],
        "Mushroom": ["mushroom", "mushrooms"],
        "Pepper": ["pepper", "peppers"],
        "Courgette": ["courgette", "courgettes"],
        "Cucumber": ["cucumber", "cucumbers"],
    },
    Category.FoodGroups.MEAT: {
        "Chicken": ["chicken", "chicken breast", "chicken thigh", "drumstick", "wings"],
        "Beef": ["beef", "beef mince", "steak", "brisket"],
        "Lamb": ["lamb", "mutton"],
        "Pork": ["pork", "bacon", "sausage", "sausages"],
        "Turkey": ["turkey"],
        "Duck": ["duck"],
    },
    Category.FoodGroups.DAIRY_AND_EGGS: {
        "Milk": ["milk"],
        "Egg": ["egg", "eggs"],
        "Cheese": ["cheese", "cheddar", "brie", "stilton"],
        "Yoghurt": ["yoghurt", "yogurt"],
        "Butter": ["butter"],
        "Cream": ["cream"],
    },
}


def _normalise_text(value):
    """
    Convert text to a lowercase searchable form.
    """
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _contains_keyword(text, keyword):
    """
    Return True when keyword appears as a separate word or phrase.

    This avoids matching tiny fragments inside unrelated words.
    Example:
    - apple matches "Royal Gala Apples"
    - pear does not match "appearing"
    """
    pattern = rf"(?<![a-z0-9]){re.escape(keyword.lower())}(?![a-z0-9])"
    return re.search(pattern, text) is not None


def infer_product_type_name(name, category):
    """
    Infer a product type name from the product name and selected category.

    Returns:
        str | None: Specific product type name when confidently detected.
    """
    text = _normalise_text(name)
    food_group = getattr(category, "food_groups", None)

    category_rules = PRODUCT_TYPE_RULES.get(food_group, {})

    for product_type_name, keywords in category_rules.items():
        if any(_contains_keyword(text, keyword) for keyword in keywords):
            return product_type_name

    return None


def get_or_create_inferred_product_type(name, category):
    """
    Return a ProductType for the product.

    Rule:
    1. Try to infer a specific product type from product name + category.
    2. If inference fails, fall back to the category name.
    3. Reuse existing ProductType rows case-insensitively.
    4. Create the ProductType if it does not already exist.
    """
    inferred_name = infer_product_type_name(name=name, category=category)
    product_type_name = inferred_name or category.name

    existing_type = ProductType.objects.filter(
        category=category,
        name__iexact=product_type_name,
    ).first()

    if existing_type:
        return existing_type

    return ProductType.objects.create(
        category=category,
        name=product_type_name,
    )