import streamlit as st
import pandas as pd
import io
import os
import json
import difflib
import openai
from datetime import datetime, timedelta

# ---------------------------
# Session State Initialization
# ---------------------------
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

# ---------------------------
# Secure API Key
# ---------------------------
openai.api_key = st.secrets["OPENAI_API_KEY"]

# ---------------------------
# Load Knowledge Base
# ---------------------------
def load_knowledge_base():
    try:
        with open("knowledge_base.json", "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        st.error("Knowledge base file not found! Make sure 'knowledge_base.json' is in the project folder.")
        return {}

knowledge_base = load_knowledge_base()

# Extract Q&A pairs from the knowledge base
def extract_qna(data):
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

qna_pairs = extract_qna(knowledge_base)

def find_best_answer(query, qna_pairs, cutoff=0.5):
    questions = [q[0] for q in qna_pairs]
    best_match = difflib.get_close_matches(query.lower(), questions, n=1, cutoff=cutoff)
    if best_match:
        for q, a in qna_pairs:
            if q == best_match[0]:
                return a
    return "I don't have information on that."

# ---------------------------
# Projection Calculation Logic
# ---------------------------
def calculate_required_days(current_weighted_date_diff, current_hours_worked, user_promised_hours, user_delay):
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

def get_upcoming_reset_date(title, current_date):
    """
    Determines the upcoming reset date based on the title.
    - If title contains "associate" or "staff", reset is November 1.
    - Otherwise (e.g., for Counsel or Partner), default reset is October 1.
    """
    title_lower = title.lower()
    if "associate" in title_lower or "staff" in title_lower:
        reset_month, reset_day = 11, 1
    else:
        reset_month, reset_day = 10, 1
    year = current_date.year
    candidate = datetime(year, reset_month, reset_day).date()
    if current_date <= candidate:
        return candidate
    else:
        return datetime(year + 1, reset_month, reset_day).date()

# ---------------------------
# App Title and Excel Upload Section
# ---------------------------
st.title("Excel File Cleaner & GPT Assistant")

uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx"])
df_cleaned = None  # For cleaned DataFrame

if uploaded_file:
    df = pd.read_excel(uploaded_file, engine='openpyxl')
    st.write("### Preview of Uploaded Data:", df.head())

    # Clean the DataFrame: drop first two rows (metadata)
    df_cleaned = df.iloc[2:].reset_index(drop=True)
    # Set the first valid row as headers
    df_cleaned.columns = df_cleaned.iloc[0]
    df_cleaned = df_cleaned[1:].reset_index(drop=True)
    # Drop completely empty columns and rows
    df_cleaned = df_cleaned.dropna(axis=1, how='all')
    df_cleaned = df_cleaned.loc[:, ~df_cleaned.columns.astype(str).str.contains('Unnamed', na=False)]
    df_cleaned.dropna(how='all', inplace=True)
    # Remove last two rows based on "Weighted Date Diff" if available
    if "Weighted Date Diff" in df_cleaned.columns:
        try:
            last_valid_index = df_cleaned[df_cleaned["Weighted Date Diff"].notna()].index[-1]
            df_cleaned = df_cleaned.iloc[:last_valid_index - 1]
        except Exception as e:
            pass

    st.write("### Preview of Cleaned Data:", df_cleaned.head())

    # Provide a download option for the cleaned Excel file
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

# Define trigger phrases for projection calculations
projection_triggers = [
    "lower my average", 
    "reduce my average", 
    "decrease my average", 
    "how long to get under 5", 
    "how to lower my average", 
    "my average days"
]

if user_input:
    st.session_state.conversation.append({"role": "user", "content": user_input})
    
    # If a file has been uploaded and the user query indicates a projection request...
    if df_cleaned is not None and any(trigger in user_input.lower() for trigger in projection_triggers):
        st.markdown("**To calculate your projection, please provide the following details:**")
        title = st.text_input("Enter your Title:")
        current_date = st.date_input("Current Date:", value=datetime.today())
        current_avg = st.number_input("Current Average Days to Enter Time:", min_value=0.0, value=16.0, step=0.1)
        entry_delay = st.number_input("What is your typical entry delay (in days)?", min_value=0.0, value=1.0, step=0.1)
        promised_hours = st.number_input("Hours entered per session:", min_value=0.0, value=7.5, step=0.5)
        
        if st.button("Calculate Projection"):
            # Attempt to extract values from the Excel file; use placeholders if extraction fails.
            if "Weighted Date Diff" in df_cleaned.columns and "Hours Worked" in df_cleaned.columns:
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
            target_date = current_date + timedelta(days=results['Required Days'])
            # Get the upcoming reset date based on title and current date
            upcoming_reset = get_upcoming_reset_date(title, current_date)
            
            # Build the projection response message with disclaimer
            disclaimer = knowledge_base.get("disclaimers", {}).get("primary_disclaimer", "")
            projection_message = f"{disclaimer}\n\nProjection Results:\n- **Current Average:** {results['Current Average']:.2f} days\n- **Projected Average:** {results['Projected Average']:.2f} days\n- **Required Additional Days of Consistent Entry:** {results['Required Days']}\n- **Projected Date to Reach Average Below 5:** {target_date.strftime('%Y-%m-%d')}\n"
            
            # If the projection target date falls after the upcoming reset date, add advisory message.
            if target_date > upcoming_reset:
                projection_message += f"\n**Note:** With your current working schedule, the projected date ({target_date.strftime('%Y-%m-%d')}) falls after your title's reset date ({upcoming_reset.strftime('%Y-%m-%d')}). This means the projection may not be achievable as calculated. Please consider increasing your entry frequency or hours to achieve a drop below 5 before the reset date."
            
            st.write("### Projection Results")
            st.markdown(projection_message)
            st.session_state.conversation.append({"role": "assistant", "content": projection_message})
    
    else:
        # If no file is uploaded or the query is not a projection trigger, use the knowledge base Q&A
        assistant_reply = find_best_answer(user_input, qna_pairs)
        st.session_state.conversation.append({"role": "assistant", "content": assistant_reply})
        st.markdown(f"**GPT:** {assistant_reply}")

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
