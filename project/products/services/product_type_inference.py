import re

from products.models import Category, ProductType


PRODUCT_TYPE_RULES = {
    # -----------------------------
    # FRUIT
    # -----------------------------
    Category.FoodGroups.FRUIT: {
        "Apple": [
            "apple", "apples", "gala", "royal gala", "braeburn", "bramley",
            "cox", "cox's orange pippin", "granny smith", "pink lady",
            "russet", "egremont russet", "discovery apple",
        ],
        "Pear": [
            "pear", "pears", "conference pear", "conference pears",
            "comice", "concorde pear",
        ],
        "Strawberry": ["strawberry", "strawberries"],
        "Raspberry": ["raspberry", "raspberries"],
        "Blueberry": ["blueberry", "blueberries"],
        "Blackberry": ["blackberry", "blackberries"],
        "Gooseberry": ["gooseberry", "gooseberries"],
        "Blackcurrant": ["blackcurrant", "blackcurrants", "black currant", "black currants"],
        "Redcurrant": ["redcurrant", "redcurrants", "red currant", "red currants"],
        "Rhubarb": ["rhubarb", "forced rhubarb"],
        "Plum": ["plum", "plums", "victoria plum", "damson", "damsons", "greengage", "greengages"],
        "Cherry": ["cherry", "cherries", "morello cherry", "morello cherries"],
    },

    # -----------------------------
    # VEGETABLES
    # -----------------------------
    Category.FoodGroups.VEGETABLES: {
        "Potato": [
            "potato", "potatoes", "new potato", "new potatoes", "maris piper",
            "king edward", "charlotte potato", "charlotte potatoes",
            "jersey royal", "jersey royals", "desiree potato", "desiree potatoes",
        ],
        "Carrot": ["carrot", "carrots", "chantenay", "chantenay carrots"],
        "Parsnip": ["parsnip", "parsnips"],
        "Swede": ["swede", "swedes"],
        "Turnip": ["turnip", "turnips"],
        "Beetroot": ["beetroot", "beetroots", "golden beetroot", "chioggia beetroot"],
        "Spring Onion": ["spring onion", "spring onions", "salad onion", "salad onions"],
        "Onion": ["onion", "onions", "red onion", "white onion", "brown onion"],
        "Leek": ["leek", "leeks"],
        "Garlic": ["garlic", "garlic bulb", "garlic bulbs", "wild garlic"],
        "Cabbage": ["cabbage", "savoy cabbage", "red cabbage", "white cabbage", "spring cabbage"],
        "Spring Greens": ["spring greens", "greens"],
        "Kale": ["kale", "curly kale", "cavolo nero"],
        "Spinach": ["spinach", "baby spinach"],
        "Chard": ["chard", "rainbow chard", "swiss chard"],
        "Lettuce": ["lettuce", "little gem", "cos lettuce", "romaine lettuce", "butterhead lettuce"],
        "Salad Leaves": ["salad leaves", "mixed leaves", "rocket", "watercress", "mizuna", "mustard leaves"],
        "Broccoli": ["broccoli", "purple sprouting broccoli", "tenderstem broccoli"],
        "Cauliflower": ["cauliflower", "cauliflowers"],
        "Brussels Sprout": ["brussels sprout", "brussels sprouts", "sprout", "sprouts"],
        "Pea": ["pea", "peas", "garden peas", "mangetout", "sugar snap", "sugar snap peas"],
        "Bean": ["bean", "beans", "broad bean", "runner bean", "french bean"],
        "Tomato": ["tomato", "tomatoes", "cherry tomato", "heritage tomato"],
        "Cucumber": ["cucumber", "cucumbers"],
        "Courgette": ["courgette", "courgettes", "zucchini"],
        "Aubergine": ["aubergine", "aubergines", "eggplant"],
        "Pepper": ["pepper", "peppers", "bell pepper", "sweet pepper"],
        "Squash": ["squash", "butternut squash", "crown prince squash", "pumpkin", "marrow"],
        "Mushroom": ["mushroom", "mushrooms", "portobello", "chestnut mushroom"],
        "Asparagus": ["asparagus", "asparagus spears"],
        "Sweetcorn": ["sweetcorn", "sweet corn", "corn on the cob"],
        "Celery": ["celery"],
        "Fennel": ["fennel"],
        "Radish": ["radish", "radishes"],
    },

    # -----------------------------
    # MEAT
    # -----------------------------
    Category.FoodGroups.MEAT: {
        "Chicken": ["chicken", "chicken breast", "chicken thigh", "drumstick", "whole chicken"],
        "Sausage": ["sausage", "sausages", "chipolata", "cumberland sausage"],
        "Beef": ["beef", "beef mince", "steak", "rump steak", "sirloin", "ribeye", "brisket"],
        "Lamb": ["lamb", "mutton", "lamb mince", "lamb chop", "lamb shoulder"],
        "Pork": ["pork", "bacon", "pork chop", "pork belly", "gammon", "ham"],
        "Turkey": ["turkey", "turkey breast", "turkey mince", "turkey crown"],
        "Duck": ["duck", "duck breast", "duck leg", "whole duck"],
        "Venison": ["venison", "venison steak", "venison mince"],
        "Game": ["game", "pheasant", "partridge", "rabbit"],
    },

    # -----------------------------
    # DAIRY
    # -----------------------------
    Category.FoodGroups.DAIRY: {
        "Milk": ["milk", "whole milk", "semi skimmed milk", "skimmed milk", "raw milk"],
        "Cheese": [
            "cheese", "cheddar", "red leicester", "stilton", "brie",
            "goat cheese", "soft cheese",
        ],
        "Yoghurt": ["yoghurt", "yogurt", "greek yoghurt"],
        "Butter": ["butter", "salted butter", "unsalted butter"],
        "Cream": ["cream", "single cream", "double cream", "clotted cream"],
        "Ice Cream": ["ice cream", "ice-cream"],
    },

    # -----------------------------
    # EGGS
    # -----------------------------
    Category.FoodGroups.EGGS: {
        "Egg": ["egg", "eggs", "duck eggs", "hen eggs", "free range eggs"],
    },

    # -----------------------------
    # BAKERY
    # -----------------------------
    Category.FoodGroups.BAKERY: {
        "Bread": ["bread", "sourdough", "wholemeal loaf", "white loaf"],
        "Pastry": ["pastry", "croissant", "pain au chocolat"],
        "Cake": ["cake", "sponge cake", "fruit cake"],
    },

    # -----------------------------
    # PRESERVES
    # -----------------------------
    Category.FoodGroups.PRESERVES: {
        "Jam": ["jam", "strawberry jam", "raspberry jam"],
        "Chutney": ["chutney", "mango chutney"],
        "Marmalade": ["marmalade"],
    },

    # -----------------------------
    # PICKLED
    # -----------------------------
    Category.FoodGroups.PICKLED: {
        "Pickle": ["pickle", "pickles"],
        "Kimchi": ["kimchi"],
        "Sauerkraut": ["sauerkraut"],
    },

    # -----------------------------
    # SWEETENERS
    # -----------------------------
    Category.FoodGroups.SWEETENERS: {
        "Honey": ["honey", "raw honey"],
        "Syrup": ["syrup", "maple syrup"],
    },

    # -----------------------------
    # BEVERAGES
    # -----------------------------
    Category.FoodGroups.BEVERAGES: {
        "Juice": ["juice", "apple juice", "orange juice"],
        "Cordial": ["cordial"],
        "Smoothie": ["smoothie"],
    },

    # -----------------------------
    # SNACKS
    # -----------------------------
    Category.FoodGroups.SNACKS: {
        "Snack": ["snack", "crisps", "chips"],
        "Confectionery": ["sweet", "fudge", "chocolate"],
    },

    # -----------------------------
    # ARTISAN
    # -----------------------------
    Category.FoodGroups.ARTISAN: {
        "Artisan Product": ["artisan", "handmade", "small batch"],
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

    This avoids matching small fragments inside unrelated words.
    Example:
    - apple matches "Royal Gala Apples"
    - pear does not match "appearing"
    """
    pattern = rf"(?<![a-z0-9]){re.escape(keyword.lower())}(?![a-z0-9])"
    return re.search(pattern, text) is not None


def infer_product_type_name(name, category):
    """
    Infer a product type name from the product name and selected category.

    The most specific matching keyword wins. This prevents broad product types
    from being returned before more specific phrases.

    Examples:
    - "Spring Onions" -> Spring Onion, not Onion
    - "Pork Sausages" -> Sausage, not Pork
    - "Royal Gala Apples" -> Apple
    """
    text = _normalise_text(name)
    food_group = getattr(category, "food_groups", None)
    category_rules = PRODUCT_TYPE_RULES.get(food_group, {})

    best_match = None

    for product_type_name, keywords in category_rules.items():
        for keyword in keywords:
            if not _contains_keyword(text, keyword):
                continue

            if best_match is None or len(keyword) > len(best_match["keyword"]):
                best_match = {
                    "product_type_name": product_type_name,
                    "keyword": keyword,
                }

    if best_match:
        return best_match["product_type_name"]

    return None


def get_or_create_inferred_product_type(name, category):
    """
    Return a ProductType for the product.

    Rule:
    1. Try to infer a specific product type from product name and category.
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