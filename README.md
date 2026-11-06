Foodmaster- 

Foodmaster is a chatbot about food and cooking. It reads a conversation from a text file, loads intent and response from JSON and uses expressions and keyword checks to choose a reply. Recipes and food facts are also loaded from separate files.

Foodmaster keeps shortterm conversation memory. When you mention a recipe, messages such as "the ingredients", "what about the method?" and "yes please" can refer to the same dish. It also remembers food preferences and dietary choices when suggesting recipes. It's stored facts are mainly about food

Project files- 

main.py - chatbot functions and the main program.
Foodmaster.ipynb - notebook implementation, script demonstration and live chat.
intents.json - intent, response  and phrase
script.txt - conversation used for the demo
recipes.json - recipe details, ingredients, steps and alternative names.
food_facts.txt - food facts
tests - automated tests for common messages and follow-up conversations.
python-version, pyproject.toml, uv.lock, .gitignore - project setup files.

Set up in VS Code -

Open this folder in vs code and open a terminal in the project folder.

In the powershell type -   uv sync

This will create the virtual environment and install the packages.

In Foodmaster.ipynb , select kernel and choose foodmaster kernel. 

Run Foodmaster in the notebook - 

Select Run All to run the chatbot and type "bye" to end the conversation

NLTK = 

Foodmaster uses NLTK VADER for sentiment detection


The Week 5 text processing section also sheows tokenisation, stopword removal, stemming, lemmatisation and POS tagging.
