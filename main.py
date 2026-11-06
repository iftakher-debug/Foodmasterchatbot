
import json
import random
import re
import sys
from pathlib import Path

try:
    from nltk.sentiment import SentimentIntensityAnalyzer
except ImportError:
    SentimentIntensityAnalyzer = None

BASE_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()

def load_script(script_name):
    with open(BASE_DIR / script_name, "r", encoding="utf-8") as file:
        return [line.strip() for line in file if line.strip()]

def load_intents(intents_file):
    with open(BASE_DIR / intents_file, "r", encoding="utf-8") as file:
        data = json.load(file)
    return data["intents"]

def load_recipes(recipes_file):
    with open(BASE_DIR / recipes_file, "r", encoding="utf-8") as file:
        data = json.load(file)
    return data["recipes"]

def load_facts(facts_file):
    facts = {}
    with open(BASE_DIR / facts_file, "r", encoding="utf-8") as file:
        for line in file:
            if ":" in line and not line.lstrip().startswith("#"):
                topic, fact = line.strip().split(":", 1)
                facts[topic.lower()] = fact.strip()
    return facts

def clean_text(text):
    text = text.lower().replace("'", "")
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return " ".join(text.split())

def has_phrase(message, phrases):
    message = clean_text(message)
    for phrase in phrases:
        phrase = clean_text(phrase)
        if phrase and re.search(r"\b" + re.escape(phrase) + r"\b", message):
            return True
    return False

def find_recipe(recipe_name, recipes):
    wanted = clean_text(recipe_name)
    for recipe in recipes:
        names = [recipe["title"]] + recipe.get("aliases", [])
        for name in names:
            if wanted == clean_text(name):
                return recipe
    return None

def find_recipe_in_message(message, recipes):
    message = clean_text(message)
    names_to_check = []
    for recipe in recipes:
        for name in [recipe["title"]] + recipe.get("aliases", []):
            names_to_check.append((clean_text(name), recipe))

    # this will check the longer names first like chicken biriyani oever biriyani".
    names_to_check.sort(key=lambda item: len(item[0]), reverse=True)
    for name, recipe in names_to_check:
        if name and re.search(r"\b" + re.escape(name) + r"\b", message):
            return recipe
    return None

def find_fact_in_message(message, facts):
    #will find a food fact topic
    message = clean_text(message)
    for topic in sorted(facts, key=len, reverse=True):
        if re.search(r"\b" + re.escape(clean_text(topic)) + r"\b", message):
            return topic, facts[topic]
    return None, None

def detect_sentiment(text):
    if SentimentIntensityAnalyzer is not None:
        try:
            score = SentimentIntensityAnalyzer().polarity_scores(text)["compound"]
            if score >= 0.05:
                return "positive"
            if score <= -0.05:
                return "negative"
            return "uncertain"
        except LookupError:
            pass

    positive_words = ["nice","noice","lovely","happy","great", "good", "excellent" "excited", "love", "amazing","cool"]
    negative_words = [ "bad","garbage", "sad", "angry", "horrendous", "upset"]
    if has_phrase(text, positive_words):
        return "positive"
    if has_phrase(text, negative_words):
        return "negative"
    return "uncertain"

def get_intent(knowledge, tag):
    for intent in knowledge:
        if intent["tag"] == tag:
            return intent
    return None

def choose_response(knowledge, tag, values=None):
    intent = get_intent(knowledge, tag)
    if not intent:
        return "Here to help you. What do you wanna know?"
    response = random.choice(intent["responses"])
    return response.format(**(values or {}))

def show_recipe(recipe, action, knowledge, memory):
    #will show the ingredient and cooking steps
    if recipe is None:
        return "Which dish you asking about? You can choose one from the menu. Just type menu"
    memory["last_recipe"] = recipe["title"]
    ingredients = ", ".join(recipe["ingredients"])
    steps = " ".join(recipe["steps"]).rstrip(" .")
    values = {
        "recipe": recipe["title"],
        "ingredients": ingredients,
        "steps": steps,
    }

    if action == "ingredients":
        memory["pending_action"] = "offer_steps"
        return choose_response(knowledge, "ingredients", values)
    if action == "steps":
        memory["pending_action"] = ""
        return choose_response(knowledge, "recipe_steps", values)

    memory["pending_action"] = ""
    return choose_response(knowledge, "recipe", values)

def get_recipe_action(message, knowledge):
    ingredients_intent = get_intent(knowledge, "ingredients")
    steps_intent = get_intent(knowledge, "recipe_steps")
    recipe_intent = get_intent(knowledge, "recipe")

    wants_ingredients = has_phrase(message, ingredients_intent.get("phrases", []))
    wants_steps = has_phrase(message, steps_intent.get("phrases", []))
    wants_both = has_phrase(message, recipe_intent.get("both_phrases", []))

    if wants_both or (wants_ingredients and wants_steps):
        return "both"
    if wants_ingredients:
        return "ingredients"
    if wants_steps:
        return "steps"
    if has_phrase(message, recipe_intent.get("phrases", [])):
        return "both"
    return ""

def is_recommendation_request(message, knowledge):
    intent = get_intent(knowledge, "recommend_recipe")
    return has_phrase(message, intent.get("phrases", []))

def handle_message(user_input, knowledge, recipes, facts, memory):
    #make response using conversation memory
    message = user_input.strip()
    cleaned = clean_text(message)

    if not cleaned:
        return "I hear you. What do you wanna talk about?"

    if re.search(r"\b(?:bye|goodbye|exit|quit)\b", cleaned):
        return "Well goodbye then, thanks for using me. See you soon"

    menu_intent = get_intent(knowledge, "menu")
    if has_phrase(message, menu_intent.get("phrases", [])):
        memory["pending_action"] = "choose_recipe"
        menu_list = ", ".join(recipe["title"] for recipe in recipes)
        return choose_response(knowledge, "menu", {"menu_list": menu_list})

    #recipe followup
    recipe = find_recipe_in_message(message, recipes)
    action = get_recipe_action(message, knowledge)
    # wont mistake a recipe for previosuly selected just because it contains the word "recipe"
    if not recipe and is_recommendation_request(message, knowledge):
        action = ""
    if recipe and not action and re.search(r"\b(?:make|cook|prepare)\b", cleaned):
        action = "steps"

    if recipe and action:
        return show_recipe(recipe, action, knowledge, memory)

    if not recipe and action:
        if memory.get("last_recipe"):
            recipe = find_recipe(memory["last_recipe"], recipes)
            return show_recipe(recipe, action, knowledge, memory)
        return "Of course. Which dish you want the ingredients or cooking steps for?"

    # short replies for example . yes please, will refer to previous request
    affirmative_intent = get_intent(knowledge, "affirmative")
    affirmative_words = [clean_text(word) for word in affirmative_intent.get("phrases", [])]
    affirmative = cleaned in affirmative_words
    if affirmative and memory.get("pending_action") == "offer_steps":
        recipe = find_recipe(memory.get("last_recipe", ""), recipes)
        return show_recipe(recipe, "steps", knowledge, memory)
    if affirmative and memory.get("pending_action") == "offer_ingredients":
        recipe = find_recipe(memory.get("last_recipe", ""), recipes)
        return show_recipe(recipe, "ingredients", knowledge, memory)
    if affirmative and memory.get("pending_action") == "choose_recipe_details":
        return "Of course you want the ingredients, the cooking steps or the full recipe?"
    if affirmative and memory.get("pending_action") == "choose_recipe":
        return "Which dish do you wanna look at? You can type its name or ask for the menu again."

    #if only mention dish, remember and give next steps
    if recipe:
        memory["last_recipe"] = recipe["title"]
        memory["pending_action"] = "choose_recipe_details"
        return ("I can help with " + recipe["title"] + ". Do you want the ingredients, the cooking steps or the full recipe?")

    #use recipe file and remembered diet
    if is_recommendation_request(message, knowledge):
        meal_match = re.search(r"\b(breakfast|brunch|lunch|dinner)\b", cleaned)
        meal = meal_match.group(1) if meal_match else ""
        choices = recipes
        if meal:
            meal_choices = [item for item in choices if meal in item.get("meal_types", [])]
            if meal_choices:
                choices = meal_choices
        diet = memory.get("diet", "")
        if diet:
            diet_choices = [item for item in choices if diet in item.get("dietary", [])]
            if diet_choices:
                choices = diet_choices

        preference = clean_text(memory.get("preference", ""))
        if "spicy" in preference:
            spicy_choices = [item for item in choices
                if any("chilli" in ingredient.lower() or "chili" in ingredient.lower()
                       or "spice" in ingredient.lower() for ingredient in item["ingredients"])]
            if spicy_choices:
                choices = spicy_choices
        selected = random.choice(choices)
        memory["last_recipe"] = selected["title"]
        memory["pending_action"] = "choose_recipe_details"
        return ("You could try " + selected["title"] + ", a " + selected["cuisine"] + " dish. Would you like the ingredients, the cooking steps or the full recipe?")

    fact_topic, fact = find_fact_in_message(message, facts)
    if fact:
        memory["last_topic"] = fact_topic
        memory["pending_action"] = ""
        return fact_topic.title() + ": " + fact

    priority = ["name", "preference", "diet", "remember", "feeling", "topic", "back_to_food", "identity", "help", "favourite_food", "cooking_interest", "cooking_ability", "balanced_meal", "food_joke", "quantity", "servings", "timer", "cooked_duration", "ingredient_count", "thanks", "greeting",]
    ordered_intents = sorted(knowledge, key=lambda item: priority.index(item["tag"]) if item["tag"] in priority else len(priority),)
    for intent in ordered_intents:
        tag = intent["tag"]
        if tag in ["default", "menu", "recipe", "ingredients", "recipe_steps", "food_fact", "recommend_recipe", "affirmative"]:
            continue
        match = re.search(intent["pattern"], message, re.IGNORECASE)
        if not match:
            continue

        values = match.groupdict()
        memory["pending_action"] = ""

        if tag == "name" and values.get("name"):
            memory["name"] = values["name"]
        elif tag == "preference" and values.get("preference"):
            memory["preference"] = values["preference"].strip()
        elif tag == "diet" and values.get("diet"):
            memory["diet"] = values["diet"].lower()
        elif tag == "remember":
            details = []
            for key in ["name", "preference", "diet"]:
                if memory.get(key):
                    details.append(key + ": " + memory[key])
            details.append("current topic: " + memory.get("topic", "food"))
            if memory.get("last_recipe"):
                details.append("last recipe: " + memory["last_recipe"])
            values["details"] = ", ".join(details) if details else "I didn't save any details yet"
        elif tag == "feeling":
            feedback = {"positive": "That's good to hear", "negative": "I'm so sorry to hear that, here's a virtual cookie for you :)", "uncertain": "It's okay, Take your time.",}
            values["feedback"] = feedback[detect_sentiment(message)]
        elif tag == "topic" and values.get("topic"):
            memory["previous_topic"] = memory.get("topic", "food")
            memory["topic"] = values["topic"].strip()
        elif tag == "back_to_food":
            values["previous_topic"] = memory.get("topic", "another topic")
            memory["previous_topic"] = values["previous_topic"]
            memory["topic"] = "food"

        try:
            return random.choice(intent["responses"]).format(**values)
        except KeyError:
            return random.choice(intent["responses"])

    #yes/no answer with no previous clear answer
    if affirmative:
        return "Sure, what do you need help with-  a recipe, ingredients, cooking steps, a food fact or maybe something else?"

    #keep it open to other subjects
    memory["pending_action"] = ""
    short_topic = message.strip(" .!?\n")
    return ("I don't have a answer for that yet, "+ "but if you tell me a little more '" + short_topic + "' and i will try to answer it")

def chatbot(script=None):
    knowledge = load_intents("intents.json")
    recipes = load_recipes("recipes.json")
    facts = load_facts("food_facts.txt")
    memory = {"name": "","preference": "","diet": "","last_recipe": "","topic": "food","previous_topic": "","last_topic": "","pending_action": "",}

    print("This is Foodmaster, the master of food. I can help with food, recipes and maybe more!!.")

    while True:
        if script is None:
            user_input = input("You: ")
        else:
            if not script:
                print("End of the conversation.")
                break
            user_input = script.pop(0)
            print("You:", user_input)

        response = handle_message(user_input, knowledge, recipes, facts, memory)
        print("Foodmaster:", response)
        if re.search(r"\b(?:bye|goodbye|exit|quit)\b", clean_text(user_input)):
            break

if __name__ == "__main__":
    if "--live" in sys.argv:
        chatbot()
    else:
        chatbot(load_script("script.txt"))
