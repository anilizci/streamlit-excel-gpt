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

# Function to find the closest matching question in JSON
def find_best_match(query, knowledge_data):
    matches = []
    
    # Convert JSON keys into a flat list
    def flatten_json(data, parent_key=""):
        """ Flatten JSON structure to create searchable key-value pairs. """
        for key, value in data.items():
            new_key = f"{parent_key} > {key}" if parent_key else key
            if isinstance(value, dict):
                flatten_json(value, new_key)
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    flatten_json({f"{new_key}[{index}]": item}, parent_key)
            else:
                matches.append((new_key, str(value)))  # Store key-value pairs for searching

    flatten_json(knowledge_data)

    # Extract keys and values
    keys = [match[0] for match in matches]
    values = {match[0]: match[1] for match in matches}

    # Use fuzzy matching to find the closest key
    best_match = difflib.get_close_matches(query.lower(), keys, n=1, cutoff=0.3)
    return values.get(best_match[0], None) if best_match else None

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
    relevant_info = find_best_match(user_input, knowledge_base)

    if not relevant_info:
        gpt_response = "I don't have information on that."
    else:
        messages = [
            {"role": "system", "content": "You are an AI assistant that ONLY answers based on the provided knowledge base. "
                                          "If the answer is not in the knowledge base, reply with: 'I don't have information on that.'"},
            {"role": "system", "content": f"Relevant knowledge found:\n\n{relevant_info}"},
            {"role": "user", "content": user_input}
        ]

        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages
            )

            gpt_response = response.choices[0].message.content
        except Exception as e:
            gpt_response = f"Error communicating with OpenAI: {str(e)}"

    # Display GPT's response
    st.write("GPT's Response:", gpt_response)
