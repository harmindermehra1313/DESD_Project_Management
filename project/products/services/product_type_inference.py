import re

from products.models import Category, ProductType


PRODUCT_TYPE_RULES = {
    Category.FoodGroups.FRUIT: {
        "Apple": [
            "apple",
            "apples",
            "gala",
            "royal gala",
            "braeburn",
            "bramley",
            "cox",
            "cox's orange pippin",
            "granny smith",
            "pink lady",
            "russet",
            "egremont russet",
            "discovery apple",
        ],
        "Pear": [
            "pear",
            "pears",
            "conference pear",
            "conference pears",
            "comice",
            "concorde pear",
        ],
        "Strawberry": [
            "strawberry",
            "strawberries",
        ],
        "Raspberry": [
            "raspberry",
            "raspberries",
        ],
        "Blueberry": [
            "blueberry",
            "blueberries",
        ],
        "Blackberry": [
            "blackberry",
            "blackberries",
        ],
        "Gooseberry": [
            "gooseberry",
            "gooseberries",
        ],
        "Blackcurrant": [
            "blackcurrant",
            "blackcurrants",
            "black currant",
            "black currants",
        ],
        "Redcurrant": [
            "redcurrant",
            "redcurrants",
            "red currant",
            "red currants",
        ],
        "Rhubarb": [
            "rhubarb",
            "forced rhubarb",
        ],
        "Plum": [
            "plum",
            "plums",
            "victoria plum",
            "damson",
            "damsons",
            "greengage",
            "greengages",
        ],
        "Cherry": [
            "cherry",
            "cherries",
            "morello cherry",
            "morello cherries",
        ],
    },

    Category.FoodGroups.VEGETABLES: {
        "Potato": [
            "potato",
            "potatoes",
            "new potato",
            "new potatoes",
            "maris piper",
            "king edward",
            "charlotte potato",
            "charlotte potatoes",
            "jersey royal",
            "jersey royals",
            "desiree potato",
            "desiree potatoes",
        ],
        "Carrot": [
            "carrot",
            "carrots",
            "chantenay",
            "chantenay carrots",
        ],
        "Parsnip": [
            "parsnip",
            "parsnips",
        ],
        "Swede": [
            "swede",
            "swedes",
        ],
        "Turnip": [
            "turnip",
            "turnips",
        ],
        "Beetroot": [
            "beetroot",
            "beetroots",
            "golden beetroot",
            "chioggia beetroot",
        ],
        "Spring Onion": [
            "spring onion",
            "spring onions",
            "salad onion",
            "salad onions",
        ],
        "Onion": [
            "onion",
            "onions",
            "red onion",
            "red onions",
            "white onion",
            "white onions",
            "brown onion",
            "brown onions",
        ],
        "Leek": [
            "leek",
            "leeks",
        ],
        "Garlic": [
            "garlic",
            "garlic bulb",
            "garlic bulbs",
            "wild garlic",
        ],
        "Cabbage": [
            "cabbage",
            "cabbages",
            "savoy cabbage",
            "red cabbage",
            "white cabbage",
            "spring cabbage",
        ],
        "Spring Greens": [
            "spring greens",
            "greens",
        ],
        "Kale": [
            "kale",
            "curly kale",
            "cavolo nero",
        ],
        "Spinach": [
            "spinach",
            "baby spinach",
        ],
        "Chard": [
            "chard",
            "rainbow chard",
            "swiss chard",
        ],
        "Lettuce": [
            "lettuce",
            "lettuces",
            "little gem",
            "cos lettuce",
            "romaine lettuce",
            "butterhead lettuce",
        ],
        "Salad Leaves": [
            "salad leaves",
            "mixed leaves",
            "rocket",
            "watercress",
            "mizuna",
            "mustard leaves",
        ],
        "Broccoli": [
            "broccoli",
            "purple sprouting broccoli",
            "tenderstem broccoli",
        ],
        "Cauliflower": [
            "cauliflower",
            "cauliflowers",
        ],
        "Brussels Sprout": [
            "brussels sprout",
            "brussels sprouts",
            "sprout",
            "sprouts",
        ],
        "Pea": [
            "pea",
            "peas",
            "garden peas",
            "mangetout",
            "sugar snap",
            "sugar snap peas",
        ],
        "Bean": [
            "bean",
            "beans",
            "broad bean",
            "broad beans",
            "runner bean",
            "runner beans",
            "french bean",
            "french beans",
        ],
        "Tomato": [
            "tomato",
            "tomatoes",
            "cherry tomato",
            "cherry tomatoes",
            "heritage tomato",
            "heritage tomatoes",
        ],
        "Cucumber": [
            "cucumber",
            "cucumbers",
        ],
        "Courgette": [
            "courgette",
            "courgettes",
            "zucchini",
        ],
        "Aubergine": [
            "aubergine",
            "aubergines",
            "eggplant",
        ],
        "Pepper": [
            "pepper",
            "peppers",
            "sweet pepper",
            "sweet peppers",
            "bell pepper",
            "bell peppers",
            "red pepper",
            "yellow pepper",
            "green pepper",
        ],
        "Squash": [
            "squash",
            "butternut squash",
            "crown prince squash",
            "pumpkin",
            "pumpkins",
            "marrow",
            "marrows",
        ],
        "Mushroom": [
            "mushroom",
            "mushrooms",
            "chestnut mushroom",
            "chestnut mushrooms",
            "portobello",
            "portobello mushrooms",
            "field mushroom",
            "field mushrooms",
        ],
        "Asparagus": [
            "asparagus",
            "asparagus spears",
        ],
        "Sweetcorn": [
            "sweetcorn",
            "sweet corn",
            "corn on the cob",
        ],
        "Celery": [
            "celery",
        ],
        "Fennel": [
            "fennel",
        ],
        "Radish": [
            "radish",
            "radishes",
        ],
    },

    Category.FoodGroups.MEAT: {
        "Chicken": [
            "chicken",
            "chicken breast",
            "chicken breasts",
            "chicken thigh",
            "chicken thighs",
            "drumstick",
            "drumsticks",
            "chicken wings",
            "whole chicken",
        ],
        "Sausage": [
            "sausage",
            "sausages",
            "pork sausage",
            "pork sausages",
            "chipolata",
            "chipolatas",
            "cumberland sausage",
            "cumberland sausages",
        ],
        "Beef": [
            "beef",
            "beef mince",
            "minced beef",
            "steak",
            "rump steak",
            "sirloin",
            "ribeye",
            "brisket",
            "braising steak",
            "stewing steak",
            "beef joint",
        ],
        "Lamb": [
            "lamb",
            "mutton",
            "lamb mince",
            "minced lamb",
            "lamb chop",
            "lamb chops",
            "lamb shoulder",
            "leg of lamb",
            "lamb shank",
        ],
        "Pork": [
            "pork",
            "bacon",
            "pork chop",
            "pork chops",
            "pork belly",
            "pork shoulder",
            "pork loin",
            "gammon",
            "ham",
        ],
        "Turkey": [
            "turkey",
            "turkey breast",
            "turkey mince",
            "minced turkey",
            "turkey crown",
        ],
        "Duck": [
            "duck",
            "duck breast",
            "duck leg",
            "whole duck",
        ],
        "Venison": [
            "venison",
            "venison steak",
            "venison mince",
            "minced venison",
        ],
        "Game": [
            "game",
            "pheasant",
            "partridge",
            "rabbit",
        ],
    },

    Category.FoodGroups.DAIRY_AND_EGGS: {
        "Milk": [
            "milk",
            "whole milk",
            "semi skimmed milk",
            "semi-skimmed milk",
            "skimmed milk",
            "raw milk",
        ],
        "Egg": [
            "egg",
            "eggs",
            "free range eggs",
            "duck eggs",
            "hen eggs",
        ],
        "Cheese": [
            "cheese",
            "cheddar",
            "mature cheddar",
            "extra mature cheddar",
            "red leicester",
            "wensleydale",
            "double gloucester",
            "stilton",
            "blue cheese",
            "brie",
            "goat cheese",
            "goats cheese",
            "goat's cheese",
            "soft cheese",
        ],
        "Yoghurt": [
            "yoghurt",
            "yogurt",
            "natural yoghurt",
            "greek yoghurt",
            "greek-style yoghurt",
        ],
        "Butter": [
            "butter",
            "salted butter",
            "unsalted butter",
        ],
        "Cream": [
            "cream",
            "single cream",
            "double cream",
            "clotted cream",
            "whipping cream",
        ],
        "Ice Cream": [
            "ice cream",
            "ice-cream",
        ],
    },

    Category.FoodGroups.SEASONAL: {
        "Vegetable Box": [
            "veg box",
            "vegetable box",
            "seasonal veg box",
            "seasonal vegetable box",
        ],
        "Fruit Box": [
            "fruit box",
            "seasonal fruit box",
        ],
        "Mixed Produce Box": [
            "produce box",
            "mixed box",
            "mixed produce",
            "seasonal box",
            "harvest box",
        ],
        "Salad Box": [
            "salad box",
            "summer salad box",
        ],
        "Soup Pack": [
            "soup pack",
            "soup mix",
            "stew pack",
            "stew mix",
        ],
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