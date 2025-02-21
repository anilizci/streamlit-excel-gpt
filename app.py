import streamlit as st
import pandas as pd
import io
import os
import json
import openai
from datetime import datetime, timedelta

# 1) Import the updated functions from chunked_embeddings
from chunked_embeddings import (
    split_text,
    create_embeddings_for_chunks,
    find_top_n_chunks,
    ask_gpt
)

# ------------------------------------------
# Set page config to wide layout
# ------------------------------------------
st.set_page_config(page_title="Average Days to Enter Time - AI Assistant", layout="wide")

# ------------------------------------------
# Inject custom CSS
# ------------------------------------------
st.markdown("""
<style>
/* Make all Streamlit buttons slightly bigger */
.stButton > button {
    padding: 0.4rem 0.8rem;
    font-size: 1rem;
    line-height: 1.4;
}

/* Make text_input fields bigger */
.stTextInput>div>div>input {
    font-size: 1rem;
    padding: 0.4rem;
    height: 2rem;
}

/* Make number_input fields bigger */
.stNumberInput>div>div>input {
    font-size: 1rem;
    padding: 0.4rem;
    height: 2rem;
}

/* Add a vertical line on the left edge of the second column (white line) */
div[data-testid="column"]:nth-of-type(2) {
    border-left: 2px solid #fff;
    padding-left: 20px;
}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------
# Session State Initialization
# ------------------------------------------
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

# ------------------------------------------
# Securely Get API Key
# ------------------------------------------
openai.api_key = st.secrets["OPENAI_API_KEY"]

# ------------------------------------------
# Load Knowledge Base from JSON
# ------------------------------------------
def load_knowledge_base():
    try:
        with open("knowledge_base.json", "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        st.error("Knowledge base file not found! Make sure 'knowledge_base.json' is in the project folder.")
        return {}

knowledge_base = load_knowledge_base()

# ------------------------------------------
# Convert the entire knowledge_base into one big text
# ------------------------------------------
def convert_json_to_text(data):
    text_fragments = []
    def traverse(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k.lower() in ["answer", "content"]:
                    if isinstance(v, str):
                        text_fragments.append(v)
                else:
                    traverse(v)
        elif isinstance(obj, list):
            for item in obj:
                traverse(item)
    traverse(data)
    return "\n".join(text_fragments)

big_knowledge_text = convert_json_to_text(knowledge_base)

# ------------------------------------------
# Our chunk-based "find_best_answer" function (top 2 chunks)
# ------------------------------------------
def find_best_answer_chunked(user_query, knowledge_text):
    if not knowledge_text.strip():
        return "I don't have information on that."
    chunks = split_text(knowledge_text, chunk_size=300, overlap=50)
    embeddings = create_embeddings_for_chunks(chunks)
    top_chunks = find_top_n_chunks(user_query, embeddings, n=2)
    combined_chunks = "\n\n".join(f"[Score: {score:.3f}] {chunk}" for score, chunk in top_chunks)
    answer = ask_gpt(user_query, combined_chunks)
    return answer

# ------------------------------------------
# Projection Calculation Logic
# ------------------------------------------
def calculate_required_days(current_weighted_date_diff, current_hours_worked, user_promised_hours, user_delay):
    current_average = current_weighted_date_diff / current_hours_worked if current_hours_worked else 0
    required_days = max(
        0,
        (4.99 * current_hours_worked - current_weighted_date_diff)
        / (user_promised_hours * user_delay - 4.99 * user_promised_hours)
    )
    required_days = round(required_days)
    projected_hours_worked = current_hours_worked + (user_promised_hours * required_days)
    projected_weighted_date_diff = current_weighted_date_diff + (user_promised_hours * user_delay * required_days)
    projected_average = (
        projected_weighted_date_diff / projected_hours_worked if projected_hours_worked else 0
    )
    return {
        'Current Average': current_average,
        'Projected Average': projected_average,
        'Required Days': required_days
    }

def get_upcoming_reset_date(title, current_date):
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

# Helper to skip weekends if needed
def add_business_days(start_date, days_needed):
    current = start_date
    business_days_passed = 0
    while business_days_passed < days_needed:
        current += timedelta(days=1)
        # Monday=0 ... Sunday=6
        if current.weekday() < 5:  # It's a weekday
            business_days_passed += 1
    return current

# ------------------------------------------
# Logo at Top-Left
# ------------------------------------------
st.markdown(
    """
    <div style="display: flex; align-items: center;">
        <h2 style="margin: 0;">SIDLEY BUSINESS INSIGHT</h2>
    </div>
    """,
    unsafe_allow_html=True
)

# ------------------------------------------
# Create two columns
# ------------------------------------------
col1, col2 = st.columns([1.2, 3], gap="medium")

# ------------------------------------------
# LEFT COLUMN (Chat Section)
# ------------------------------------------
with col1:
    st.title("Average Days to Enter Time - AI Assistant")
    user_input = st.text_input("Ask me anything about Average Days to Enter Time:")

# ------------------------------------------
# RIGHT COLUMN (Excel/Projection, Answers)
# ------------------------------------------
with col2:
    # Define trigger phrases for projection calculations (updated to include additional variations)
    projection_triggers = [
        "calculate my average",
        "lower my average", 
        "reduce my average", 
        "decrease my average", 
        "how long to get under 5", 
        "how to lower my average", 
        "my average days",
        "average is high",
        "calculate my average time",
        "project my average time",
        "average days to enter time",
        "my average days to enter time"
    ]

    # Check if the query is about calculating/projecting average time/days.
    if user_input:
        st.session_state.conversation.append({"role": "user", "content": user_input})
        
        if any(trigger in user_input.lower() for trigger in projection_triggers) or (
            "average" in user_input.lower() and 
            ("calculate" in user_input.lower() or "project" in user_input.lower() or "lower" in user_input.lower())
        ):
            uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx"])
            df_cleaned = None
            
            if uploaded_file:
                df = pd.read_excel(uploaded_file, engine='openpyxl')
                st.write("### Preview of Uploaded Data:", df.head())
                
                df_cleaned = df.iloc[2:].reset_index(drop=True)
                df_cleaned.columns = df_cleaned.iloc[0]
                df_cleaned = df_cleaned[1:].reset_index(drop=True)
                df_cleaned = df_cleaned.dropna(axis=1, how='all')
                df_cleaned = df_cleaned.loc[:, ~df_cleaned.columns.astype(str).str.contains('Unnamed', na=False)]
                df_cleaned.dropna(how='all', inplace=True)
                
                if "Weighted Date Diff" in df_cleaned.columns:
                    try:
                        last_valid_index = df_cleaned[df_cleaned["Weighted Date Diff"].notna()].index[-1]
                        df_cleaned = df_cleaned.iloc[:last_valid_index - 1]
                    except Exception:
                        pass
                
                st.write("### Preview of Cleaned Data:", df_cleaned.head())
                
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
            else:
                st.warning("Please upload an Excel file to calculate your projection.")
            
            if uploaded_file:
                st.markdown("**To calculate your projection, please provide the following details:**")
                title = st.text_input("Enter your Title:")
                
                # UPDATED: Provide a hint in parentheses
                current_date = st.date_input(
                    "Current Date (Enter the last work date on the Excel):",
                    value=datetime.today()
                )

                current_avg = st.number_input("Current Average Days to Enter Time:", min_value=0.0, value=16.0, step=0.1)
                
                entry_delay = st.number_input(
                    "When are you going to enter the time? Enter 0 for the same day, for the next day please enter 1. (entry delay)", 
                    min_value=0.0, 
                    value=1.0, 
                    step=0.1
                )
                
                promised_hours = st.number_input("Hours entered per session:", min_value=0.0, value=7.5, step=0.5)

                weekend_option = st.selectbox(
                    "Will you work only on weekdays or also on weekends?",
                    ["Weekdays only", "Weekdays + weekends"]
                )

                if st.button("Calculate Projection"):
                    if (df_cleaned is not None 
                        and "Weighted Date Diff" in df_cleaned.columns 
                        and "Hours Worked" in df_cleaned.columns):
                        try:
                            current_weighted_date_diff = pd.to_numeric(df_cleaned["Weighted Date Diff"], errors="coerce").sum()
                            current_hours_worked = pd.to_numeric(df_cleaned["Hours Worked"], errors="coerce").sum()
                        except Exception:
                            st.error("Error computing values from Excel file. Using placeholder values.")
                            current_weighted_date_diff = current_avg * 100
                            current_hours_worked = 100
                    else:
                        current_weighted_date_diff = current_avg * 100
                        current_hours_worked = 100

                    results = calculate_required_days(
                        current_weighted_date_diff,
                        current_hours_worked,
                        promised_hours,
                        entry_delay
                    )

                    required_days = results['Required Days']
                    if weekend_option == "Weekdays only":
                        target_date = add_business_days(current_date, required_days)
                    else:
                        target_date = current_date + timedelta(days=required_days)

                    upcoming_reset = get_upcoming_reset_date(title, current_date)
                    target_date_str = target_date.strftime('%m/%d/%Y')
                    upcoming_reset_str = upcoming_reset.strftime('%m/%d/%Y')

                    disclaimer = knowledge_base.get("disclaimers", {}).get("primary_disclaimer", "")
                    projection_message = (
                        f"{disclaimer}\n\n"
                        f"Projection Results:\n"
                        f"- **Current Average:** {results['Current Average']:.2f} days\n"
                        f"- **Projected Average:** {results['Projected Average']:.2f} days\n"
                        f"- **Required Additional Days (Working Days):** {required_days}\n"
                        f"- **Projected Date to Reach Average Below 5:** {target_date_str}\n"
                    )
                    
                    if target_date > upcoming_reset:
                        projection_message += (
                            f"\n**Note:** With your current working schedule, the projected date "
                            f"({target_date_str}) falls after your title's reset date "
                            f"({upcoming_reset_str}). "
                            "This means the projection may not be achievable as calculated. "
                            "Consider increasing your entry frequency or hours."
                        )
                    
                    st.session_state.conversation.append({"role": "assistant", "content": projection_message})

        else:
            assistant_reply = find_best_answer_chunked(user_input, big_knowledge_text)
            st.session_state.conversation.append({"role": "assistant", "content": assistant_reply})

        latest_gpt_answer = None
        for msg in reversed(st.session_state.conversation):
            if msg["role"] == "assistant":
                latest_gpt_answer = msg["content"]
                break

        if latest_gpt_answer:
            st.markdown(f"**GPT:** {latest_gpt_answer}")

    with st.expander("Show Full Conversation History", expanded=False):
        for msg in st.session_state.conversation:
            if msg["role"] == "system":
                continue
            role_label = "GPT" if msg["role"] == "assistant" else "You"
            st.markdown(f"**{role_label}:** {msg['content']}")

    if st.button("Clear Conversation"):
        st.session_state.conversation = [
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that ONLY answers based on the provided knowledge base. "
                    "If the answer is not in the knowledge base, reply with: 'I don't have information on that.'"
                )
            }
        ]
        st.experimental_rerun()
