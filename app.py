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
        {"role": "system", "content": "You are an AI assistant that uses a provided knowledge base to answer questions. Remember the context of the conversation to handle follow-up questions."}
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

# Enhanced matching functions
def find_best_matches_prioritize_faq(query, kb_items, top_n=3, cutoff=0.2):
    """
    Prioritize FAQs in the matching process.
    """
    faq_prefix = "knowledge_base > sections > 6. Intapp FAQ > questions > "  # Adjust based on JSON structure
    faq_items = [item for item in kb_items if item[0].lower().startswith(faq_prefix)]
    other_items = [item for item in kb_items if not item[0].lower().startswith(faq_prefix)]
    
    # First, search within FAQs
    faq_combined = [f"{k}: {v}".lower() for k, v in faq_items]
    faq_matches = difflib.get_close_matches(query.lower(), faq_combined, n=top_n, cutoff=cutoff)
    
    # Then, search within other knowledge
    other_combined = [f"{k}: {v}".lower() for k, v in other_items]
    other_matches = difflib.get_close_matches(query.lower(), other_combined, n=top_n, cutoff=cutoff)
    
    # Combine results, ensuring no duplicates
    combined_matches = faq_matches + other_matches
    unique_matches = []
    seen = set()
    for match in combined_matches:
        if match not in seen:
            unique_matches.append(match)
            seen.add(match)
        if len(unique_matches) >= top_n:
            break
    
    # Find corresponding (key, value) pairs
    result = []
    for match in unique_matches:
        for k, v in kb_items:
            combined = f"{k}: {v}".lower()
            if combined == match:
                result.append((k, v))
                break
    return result

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
        # Search for relevant knowledge in the JSON file using prioritized matching
        best_matches = find_best_matches_prioritize_faq(user_input, kb_items, top_n=3, cutoff=0.2)

        if not best_matches:
            assistant_reply = "I don't have information on that."
            # Append assistant reply to conversation history
            st.session_state.conversation.append({"role": "assistant", "content": assistant_reply})
        else:
            # Combine relevant knowledge
            context = "\n".join([f"[{k}]: {v}" for (k, v) in best_matches])
            st.session_state.conversation.append(
                {"role": "system", "content": f"Relevant knowledge found:\n{context}"}
            )

            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",  # Ensure correct model name
                    messages=st.session_state.conversation
                )
                assistant_reply = response.choices[0].message.content
                # Append assistant reply to conversation history
                st.session_state.conversation.append({"role": "assistant", "content": assistant_reply})
            except Exception as e:
                assistant_reply = f"Error communicating with OpenAI: {str(e)}"
                st.session_state.conversation.append({"role": "assistant", "content": assistant_reply})

    # Display GPT's response
    st.write("### **GPT's Response:**", assistant_reply)

# Display conversation history
st.subheader("Conversation History")

# Function to get the latest user and assistant messages
def get_latest_exchange(conversation):
    latest_user = None
    latest_assistant = None
    for msg in reversed(conversation):
        if msg['role'] == 'assistant' and latest_assistant is None:
            latest_assistant = msg['content']
        elif msg['role'] == 'user' and latest_user is None:
            latest_user = msg['content']
        if latest_user and latest_assistant:
            break
    return latest_user, latest_assistant

latest_user, latest_assistant = get_latest_exchange(st.session_state.conversation)

# Display only the latest exchange
if latest_user and latest_assistant:
    st.markdown(f"**You:** {latest_user}")
    st.markdown(f"**GPT:** {latest_assistant}")

# Provide an expandable section to view full history
with st.expander("Show Full Conversation History"):
    for msg in st.session_state.conversation:
        if msg['role'] == 'user':
            st.markdown(f"**You:** {msg['content']}")
        elif msg['role'] == 'assistant':
            st.markdown(f"**GPT:** {msg['content']}")
        elif msg['role'] == 'system':
            # Optionally display system messages differently or skip them
            pass  # Currently skipping system messages

# Option to clear conversation
if st.button("Clear Conversation"):
    st.session_state.conversation = [
        {"role": "system", "content": "You are an AI assistant that uses a provided knowledge base to answer questions. Remember the context of the conversation to handle follow-up questions."}
    ]
    st.experimental_rerun()
