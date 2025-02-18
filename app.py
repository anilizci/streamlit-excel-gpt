import streamlit as st
import pandas as pd
import io
import os
import json
import difflib
import openai
from datetime import datetime, timedelta

# Initialize session state for conversation history
if 'conversation' not in st.session_state:
    st.session_state.conversation = [
        {
            "role": "system",
            "content": (
                "You are an AI assistant that ONLY answers based on the provided knowledge base. "
                "If the answer is not in the knowledge base, reply with: 'I don't have information on that.'"
            )
        }
    ]

# Securely get OpenAI API key from Streamlit secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]

# ---------------------------
# Knowledge Base Loading
# ---------------------------
def load_knowledge_base():
    try:
        with open("knowledge_base.json", "r", encoding="utf-8") as file:
            return json.load(file)  # Load JSON as a dictionary
    except FileNotFoundError:
        st.error("Knowledge base file not found! Make sure 'knowledge_base.json' is in the project folder.")
        return {}

knowledge_base = load_knowledge_base()

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

# Extract question-answer pairs from the knowledge base
qna_pairs = extract_qna(knowledge_base)

def find_best_answer(query, qna_pairs, cutoff=0.5):
    """
    Find the best-matching question from the knowledge base and return the corresponding answer.
    """
    questions = [q[0] for q in qna_pairs]
    best_match = difflib.get_close_matches(query.lower(), questions, n=1, cutoff=cutoff)
    if best_match:
        for q, a in qna_pairs:
            if q == best_match[0]:
                return a  # Return the exact stored answer
    return "I don't have information on that."

# ---------------------------
# Projection Calculation Logic
# ---------------------------
def calculate_required_days(current_weighted_date_diff, current_hours_worked, user_promised_hours, user_delay):
    """
    Calculates the number of additional days required to lower the average days to enter time to below 5.
    Uses the formula:
      required_days = max(0, (4.99 * current_hours_worked - current_weighted_date_diff) /
                             (user_promised_hours * user_delay - 4.99 * user_promised_hours))
    and then computes the new projected average.
    """
    current_average = current_weighted_date_diff / current_hours_worked if current_hours_worked else 0
    required_days = max(0, (4.99 * current_hours_worked - current_weighted_date_diff) /
                           (user_promised_hours * user_delay - 4.99 * user_promised_hours))
    required_days = round(required_days)
    projected_hours_worked = current_hours_worked + (user_promised_hours * required_days)
    projected_weighted_date_diff = current_weighted_date_diff + (user_promised_hours * user_delay * required_days)
    projected_average = projected_weighted_date_diff / projected_hours_worked if projected_hours_worked else 0
    return {
        'Current Average': current_average,
        'Projected Average': projected_average,
        'Required Days': required_days
    }

# ---------------------------
# App Title and Excel Upload Section
# ---------------------------
st.title("Excel File Cleaner & GPT Assistant")

uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx"])
df_cleaned = None  # Initialize variable for cleaned DataFrame

if uploaded_file:
    df = pd.read_excel(uploaded_file, engine='openpyxl')
    st.write("### Preview of Uploaded Data:", df.head())

    # Drop the first two rows (metadata)
    df_cleaned = df.iloc[2:].reset_index(drop=True)

    # Set the first valid row as column headers
    df_cleaned.columns = df_cleaned.iloc[0]
    df_cleaned = df_cleaned[1:].reset_index(drop=True)

    # Drop completely empty columns
    df_cleaned = df_cleaned.dropna(axis=1, how='all')

    # Drop columns that contain "Unnamed"
    df_cleaned = df_cleaned.loc[:, ~df_cleaned.columns.astype(str).str.contains('Unnamed', na=False)]

    # Drop fully empty rows
    df_cleaned.dropna(how='all', inplace=True)

    # Identify and remove last two rows based on "Weighted Date Diff" column
    if "Weighted Date Diff" in df_cleaned.columns:
        try:
            last_valid_index = df_cleaned[df_cleaned["Weighted Date Diff"].notna()].index[-1]
            df_cleaned = df_cleaned.iloc[:last_valid_index - 1]
        except Exception as e:
            pass

    st.write("### Preview of Cleaned Data:", df_cleaned.head())

    # Convert cleaned DataFrame to Excel format for download
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_cleaned.to_excel(writer, index=False, sheet_name="Cleaned Data")
    output.seek(0)

    st.download_button(
        label="Download Cleaned Excel",
        data=output,
        file_name="cleaned_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ---------------------------
# GPT Chat Interface Section
# ---------------------------
st.header("Chat with GPT (Based on Knowledge Base)")

user_input = st.text_input("Ask GPT anything:")

if user_input:
    st.session_state.conversation.append({"role": "user", "content": user_input})
    
    # Define phrases that trigger the projection calculation branch
    projection_triggers = [
        "lower my average", 
        "reduce my average", 
        "decrease my average", 
        "how long to get under 5", 
        "how to lower my average", 
        "my average days"
    ]
    
    if any(trigger in user_input.lower() for trigger in projection_triggers):
        st.markdown("**To calculate your projection, please provide the following details:**")
        title = st.text_input("Enter your Title:")
        current_date = st.date_input("Current Date:", value=datetime.today())
        current_avg = st.number_input("Current Average Days to Enter Time:", min_value=0.0, value=16.0, step=0.1)
        entry_delay = st.number_input("What is your typical entry delay (in days)?", min_value=0.0, value=1.0, step=0.1)
        promised_hours = st.number_input("Hours entered per session:", min_value=0.0, value=7.5, step=0.5)
        
        if st.button("Calculate Projection"):
            # If an Excel file was uploaded and cleaned, attempt to compute values from it;
            # otherwise, use placeholder values.
            if df_cleaned is not None and "Weighted Date Diff" in df_cleaned.columns and "Hours Worked" in df_cleaned.columns:
                try:
                    current_weighted_date_diff = pd.to_numeric(df_cleaned["Weighted Date Diff"], errors="coerce").sum()
                    current_hours_worked = pd.to_numeric(df_cleaned["Hours Worked"], errors="coerce").sum()
                except Exception as e:
                    st.error("Error computing values from Excel file. Using placeholder values.")
                    current_weighted_date_diff = current_avg * 100
                    current_hours_worked = 100
            else:
                current_weighted_date_diff = current_avg * 100
                current_hours_worked = 100

            results = calculate_required_days(current_weighted_date_diff, current_hours_worked, promised_hours, entry_delay)
            st.write("### Projection Results")
            st.write(f"**Current Average:** {results['Current Average']:.2f} days")
            st.write(f"**Projected Average:** {results['Projected Average']:.2f} days")
            st.write(f"**Required Additional Days of Consistent Entry:** {results['Required Days']}")
            target_date = current_date + timedelta(days=results['Required Days'])
            st.write(f"**Projected Date to Reach Average Below 5:** {target_date.strftime('%Y-%m-%d')}")
            
            assistant_reply = (
                f"Projection Results: Current Average: {results['Current Average']:.2f} days, "
                f"Projected Average: {results['Projected Average']:.2f} days, "
                f"Required Days: {results['Required Days']}, "
                f"Target Date: {target_date.strftime('%Y-%m-%d')}."
            )
            st.session_state.conversation.append({"role": "assistant", "content": assistant_reply})
    else:
        # Normal Q&A: Find answer from the knowledge base
        assistant_reply = find_best_answer(user_input, qna_pairs)
        st.session_state.conversation.append({"role": "assistant", "content": assistant_reply})

# ---------------------------
# Display Conversation History
# ---------------------------
st.subheader("Conversation History")
if len(st.session_state.conversation) > 1:
    st.markdown(f"**You:** {st.session_state.conversation[-2]['content']}")
    st.markdown(f"**GPT:** {st.session_state.conversation[-1]['content']}")

with st.expander("Show Full Conversation History"):
    for msg in st.session_state.conversation:
        if msg['role'] in ["user", "assistant"]:
            st.markdown(f"**{msg['role'].capitalize()}**: {msg['content']}")

# ---------------------------
# Clear Conversation Button
# ---------------------------
if st.button("Clear Conversation"):
    st.session_state.conversation = [
        {
            "role": "system",
            "content": "You are an AI assistant that uses a provided knowledge base to answer questions."
        }
    ]
    st.experimental_rerun()
