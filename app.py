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

# Function to extract only questions and answers from the JSON
def extract_qna(data):
    """Extracts all questions and answers from a structured JSON knowledge base."""
    qna_list = []
    
    def traverse_json(obj):
        if isinstance(obj, dict):
            if "question" in obj and "answer" in obj:
                qna_list.append((obj["question"].lower(), obj["answer"]))
            for value in obj.values():
                traverse_json(value)
        elif isinstance(obj, list):
            for item in obj:
                traverse_json(item)
    
    traverse_json(data)
    return qna_list

# Extract question-answer pairs
qna_pairs = extract_qna(knowledge_base)

# Function to find the best-matching question and return the exact answer
def find_best_answer(query, qna_pairs, cutoff=0.5):
    """
    Find the best-matching question from the knowledge base and return the corresponding answer.
    """
    questions = [q[0] for q in qna_pairs]  # Extract only the question texts
    best_match = difflib.get_close_matches(query.lower(), questions, n=1, cutoff=cutoff)

    if best_match:
        for q, a in qna_pairs:
            if q == best_match[0]:  
                return a  # Return the exact stored answer
    return "I don't have information on that."  # Default response if no match is found

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
        # Retrieve the exact answer from the knowledge base
        assistant_reply = find_best_answer(user_input, qna_pairs)

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
