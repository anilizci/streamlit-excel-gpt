# Initialize session state for conversation history
if 'conversation' not in st.session_state:
    st.session_state.conversation = [
        {"role": "system", "content": "You are an AI assistant that uses a provided knowledge base to answer questions. Remember the context of the conversation to handle follow-up questions."}
    ]

import streamlit as st
import pandas as pd
import io
import os
import json
import difflib
import openai  # typically we import openai directly

# 1. Set your API key
openai.api_key = st.secrets["OPENAI_API_KEY"]  # or os.getenv("OPENAI_API_KEY")

def load_knowledge_base():
    try:
        with open("knowledge_base.json", "r", encoding="utf-8") as file:
            return json.load(file)  # dict or list
    except FileNotFoundError:
        st.error("Knowledge base file not found!")
        return {}

knowledge_base = load_knowledge_base()

# Flatten JSON
def flatten_json(data, parent_key="", sep=" > "):
    items = {}
    if isinstance(data, dict):
        for k, v in data.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            items.update(flatten_json(v, new_key, sep=sep))
    elif isinstance(data, list):
        for index, v in enumerate(data):
            new_key = f"{parent_key}[{index}]"
            items.update(flatten_json(v, new_key, sep=sep))
    else:
        items[parent_key] = str(data)
    return items

flat_knowledge_base = flatten_json(knowledge_base)

# Instead of matching on keys only, build a list of (key, value) pairs
kb_items = list(flat_knowledge_base.items())  # [(key_path, text), ...]

def find_best_matches(query, kb_items, top_n=3, cutoff=0.2):
    """
    Return the top_n best fuzzy matches based on the KB *values*, not keys.
    We match query against each value's text, then pick the top 3 or so.
    """
    # Extract just the text from each (key, value) pair
    texts = [item[1].lower() for item in kb_items]
    # Use difflib to get the closest matches from the list of texts
    # (You might do something else like "difflib.SequenceMatcher(None, query, t).ratio()"
    #  or a better approach with embeddings.)
    matches = difflib.get_close_matches(query.lower(), texts, n=top_n, cutoff=cutoff)
    
    # Find the actual (key, value) pairs that correspond to these text matches
    result = []
    for match in matches:
        for k, v in kb_items:
            if v.lower() == match:  # exact match of the text
                result.append((k, v))
                break
    return result

# Streamlit code
st.title("Excel File Cleaner & GPT Assistant")

uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx"])
if uploaded_file:
    # ... your existing cleaning code ...
    pass

st.header("Chat with GPT (Only Based on Knowledge Base)")
user_input = st.text_input("Ask GPT anything:")

if user_input:
    # 2. Find multiple relevant matches
    best_matches = find_best_matches(user_input, kb_items, top_n=3, cutoff=0.2)

    if not best_matches:
        # No fuzzy match
        st.write("GPT's Response:", "I don't have information on that.")
    else:
        # Combine relevant info from the best matches
        context = "\n".join([f"[{k}]: {v}" for (k, v) in best_matches])

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that ONLY answers based on the provided knowledge base. "
                    "If the answer is not in the knowledge base, reply with: 'I don't have information on that.'"
                )
            },
            {
                "role": "system",
                "content": f"Relevant knowledge found:\n\n{context}"
            },
            {
                "role": "user",
                "content": user_input
            }
        ]

        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",  # or "gpt-4"
                messages=messages
            )
            gpt_response = response.choices[0].message.content
        except Exception as e:
            gpt_response = f"Error communicating with OpenAI: {str(e)}"

        st.write("GPT's Response:", gpt_response)
