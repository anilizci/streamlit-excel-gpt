import streamlit as st
import pandas as pd
import io
import os
import json
import difflib
from openai import OpenAI

# Securely get OpenAI API key from Streamlit secrets
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("OpenAI API key is missing! Add it to Streamlit secrets.")
    st.stop()

client = OpenAI(api_key=api_key)

# Load knowledge base from JSON file
def load_knowledge_base():
    try:
        with open("knowledge_base.json", "r", encoding="utf-8") as file:
            return json.load(file)  # Load JSON as a dictionary
    except FileNotFoundError:
        st.error("Knowledge base file not found! Make sure 'knowledge_base.json' is in the project folder.")
        return {}

knowledge_base = load_knowledge_base()

# Function to flatten JSON structure for improved search
def flatten_json(data, parent_key="", sep=" > "):
    """ Converts a nested JSON into a searchable dictionary with key paths """
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

# Flatten the knowledge base for better searching
flat_knowledge_base = flatten_json(knowledge_base)

# Function to find the closest match from the JSON knowledge base
def find_best_match(query, knowledge_data):
    keys = list(knowledge_data.keys())  # Extract all possible keys (questions)
    matches = difflib.get_close_matches(query.lower(), keys, n=1, cutoff=0.2)  # Allow fuzzy matching
    return matches[0] if matches else None

# App title
st.title("Excel File Cleaner & GPT Assistant")

# File upload
uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx"])
df_cleaned = None  # Initialize df_cleaned to be used later

if uploaded_file:
    df = pd.read_excel(uploaded_file, engine='openpyxl')
    st.write("Preview of Uploaded Data:", df.head())

    # Drop first two rows (metadata rows)
    df_cleaned = df.iloc[2:].reset_index(drop=True)

    # Set the first valid row as column headers
    df_cleaned.columns = df_cleaned.iloc[0]  # Assign first row as headers
    df_cleaned = df_cleaned[1:].reset_index(drop=True)  # Remove the now-redundant header row

    # Drop completely empty columns
    df_cleaned = df_cleaned.dropna(axis=1, how='all')

    # Drop columns that contain "Unnamed"
    df_cleaned = df_cleaned.loc[:, ~df_cleaned.columns.astype(str).str.contains('Unnamed', na=False)]

    # Drop fully empty rows
    df_cleaned.dropna(how='all', inplace=True)

    # Identify and remove last two rows based on "Weighted Date Diff" column
    if "Weighted Date Diff" in df_cleaned.columns:
        last_valid_index = df_cleaned[df_cleaned["Weighted Date Diff"].notna()].index[-1]
        df_cleaned = df_cleaned.iloc[:last_valid_index - 1]  # Remove last two rows

    st.write("Preview of Cleaned Data:", df_cleaned.head())

    # Convert cleaned DataFrame to Excel format
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_cleaned.to_excel(writer, index=False, sheet_name="Cleaned Data")
    output.seek(0)

    # Provide download button for Excel file
    st.download_button(
        label="Download Cleaned Excel",
        data=output,
        file_name="cleaned_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# Section: GPT Chat Interface
st.header("Chat with GPT (Only Based on Knowledge Base)")

user_input = st.text_input("Ask GPT anything:")

if user_input:
    # Search for relevant knowledge in the JSON file
    best_match = find_best_match(user_input, flat_knowledge_base)

    if not best_match:
        gpt_response = "I don't have information on that."
    else:
        relevant_info = flat_knowledge_base[best_match]
        messages = [
            {"role": "system", "content": "You are an AI assistant that ONLY answers based on the provided knowledge base. "
                                          "If the answer is not in the knowledge base, reply with: 'I don't have information on that.'"},
            {"role": "system", "content": f"Relevant knowledge found:\n\n{relevant_info}"},
            {"role": "user", "content": user_input}
        ]

        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=messages
            )

            gpt_response = response.choices[0].message.content
        except Exception as e:
            gpt_response = f"Error communicating with OpenAI: {str(e)}"

    # Display GPT's response
    st.write("GPT's Response:", gpt_response)
