import streamlit as st
import pandas as pd
import io
import os
import json
import difflib
import openai  # Ensure openai==0.28.0 is installed

# Initialize session state for conversation history
if 'conversation' not in st.session_state:
    st.session_state.conversation = [
        {"role": "system", "content": "You are an AI assistant that ONLY answers based on the provided knowledge base. If the answer is not in the knowledge base, reply with: 'I don't have information on that.'"}
    ]

# Securely get OpenAI API key from Streamlit secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]

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
    """Converts a nested JSON into a searchable dictionary with key paths."""
    items = {}
    
    if isinstance(data, dict):
        for k, v in data.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            items.update(flatten_json(v, new_key, sep=sep))
    elif isinstance(data, list):
        for index, v in enumerate(data):
            if isinstance(v, dict):
                for sub_k, sub_v in v.items():
                    sub_key = f"{parent_key}[{index}] > {sub_k}"
                    items.update(flatten_json(sub_v, sub_key, sep=sep))
            else:
                new_key = f"{parent_key}[{index}]"
                items.update(flatten_json(v, new_key, sep=sep))
    else:
        items[parent_key] = str(data)
    
    return items

# Flatten the knowledge base for better searching
flat_knowledge_base = flatten_json(knowledge_base)

# Build a list of (key, value) pairs
kb_items = list(flat_knowledge_base.items())  # [(key_path, text), ...]

# Function to find the best answer for a user query with improved fuzzy matching
def find_best_answer(query, kb_items, cutoff=0.4):
    """
    Find the best-matching answer from the knowledge base, even if phrased differently.
    """
    keys = [item[0].lower() for item in kb_items]  # Extract all keys/questions
    best_match = difflib.get_close_matches(query.lower(), keys, n=1, cutoff=cutoff)

    if best_match:
        for k, v in kb_items:
            if k.lower() == best_match[0]:
                return v  # Return the matched answer
    return None  # No relevant answer found

# App title
st.title("Excel File Cleaner & GPT Assistant")

# File upload
uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx"])
df_cleaned = None  # Initialize df_cleaned to be used later

if uploaded_file:
    df = pd.read_excel(uploaded_file, engine='openpyxl')
    st.write("### Preview of Uploaded Data:", df.head())

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

    st.write("### Preview of Cleaned Data:", df_cleaned.head())

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
st.header("Chat with GPT (Based on Knowledge Base)")

user_input = st.text_input("Ask GPT anything:")

if user_input:
    # Append user message to conversation history
    st.session_state.conversation.append({"role": "user", "content": user_input})

    with st.spinner("GPT is generating a response..."):
        # Retrieve the best-matching answer from the knowledge base
        assistant_reply = find_best_answer(user_input, kb_items)

        if not assistant_reply:
            assistant_reply = "I don't have information on that."

    # Append assistant reply to conversation history
    st.session_state.conversation.append({"role": "assistant", "content": assistant_reply})

# Display only the conversation history
st.subheader("Conversation History")

# Display latest user message and GPT response only
if len(st.session_state.conversation) > 1:
    st.markdown(f"**You:** {st.session_state.conversation[-2]['content']}")
    st.markdown(f"**GPT:** {st.session_state.conversation[-1]['content']}")

# Expandable full conversation history
with st.expander("Show Full Conversation History"):
    for msg in st.session_state.conversation:
        if msg['role'] in ["user", "assistant"]:
            st.markdown(f"**{msg['role'].capitalize()}**: {msg['content']}")

# Clear conversation button
if st.button("Clear Conversation"):
    st.session_state.conversation = [{"role": "system", "content": "You are an AI assistant that uses a provided knowledge base to answer questions."}]
    st.experimental_rerun()
