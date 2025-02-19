import streamlit as st
import pandas as pd
import io
import os
import json
import difflib
import openai
from datetime import datetime, timedelta

# ---------------------------
# Page Configuration & Custom Styling
# ---------------------------
st.set_page_config(
    page_title="Average Days to Enter Time - AI Assistant",
    page_icon=":bar_chart:",
    layout="wide"
)

# Inject some CSS to hide Streamlit branding and tweak the style
st.markdown(
    """
    <style>
    /* Hide Streamlit menu & footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Make the main page background slightly off-white for a professional look */
    .main {
        background-color: #F7F7F7;
        padding: 20px;
    }

    /* Style primary buttons (e.g., 'Calculate Projection') */
    .stButton>button {
        background-color: #0A5A9C; /* Corporate-like navy color */
        color: white;
        border-radius: 6px;
        padding: 0.6rem 1.2rem;
        font-weight: 500;
        font-size: 1rem;
        border: none;
    }

    /* Style secondary buttons (e.g., 'Download') */
    .stDownloadButton>button {
        background-color: #444444;
        color: white;
        border-radius: 6px;
        padding: 0.6rem 1.2rem;
        font-weight: 500;
        font-size: 1rem;
        border: none;
    }

    /* Style the expander header for conversation history */
    .streamlit-expanderHeader {
        font-size: 1rem;
        font-weight: 600;
        color: #0A5A9C;
    }
    </style>
    """,
    unsafe_allow_html=True
)

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
# Securely Get API Key
# ---------------------------
openai.api_key = st.secrets["OPENAI_API_KEY"]

# ---------------------------
# Load Knowledge Base from JSON
# ---------------------------
def load_knowledge_base():
    try:
        with open("knowledge_base.json", "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        st.error("Knowledge base file not found! Make sure 'knowledge_base.json' is in the project folder.")
        return {}

knowledge_base = load_knowledge_base()

# ---------------------------
# Extract Q&A Pairs from Knowledge Base
# ---------------------------
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
    """
    Determines the upcoming reset date based on the title.
    For associates/staff, resets on November 1; for counsel/partners, resets on October 1.
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
# Main Page Title
# ---------------------------
st.title("Average Days to Enter Time - AI Assistant")

# ---------------------------
# 1) File Upload & Cleaning Section
# ---------------------------
st.markdown("## 1) Upload and Clean Your Excel File")

uploaded_file = st.file_uploader("Upload an Excel file (XLSX format):", type=["xlsx"])
df_cleaned = None

if uploaded_file:
    df = pd.read_excel(uploaded_file, engine='openpyxl')
    st.write("### Preview of Uploaded Data:")
    st.dataframe(df.head(10))

    # Clean the data: drop metadata rows, set headers, remove empty columns/rows.
    df_cleaned = df.iloc[2:].reset_index(drop=True)
    df_cleaned.columns = df_cleaned.iloc[0]
    df_cleaned = df_cleaned[1:].reset_index(drop=True)
    df_cleaned = df_cleaned.dropna(axis=1, how='all')
    df_cleaned = df_cleaned.loc[:, ~df_cleaned.columns.astype(str).str.contains('Unnamed', na=False)]
    df_cleaned.dropna(how='all', inplace=True)
    
    # Remove last two rows based on "Weighted Date Diff"
    if "Weighted Date Diff" in df_cleaned.columns:
        try:
            last_valid_index = df_cleaned[df_cleaned["Weighted Date Diff"].notna()].index[-1]
            df_cleaned = df_cleaned.iloc[:last_valid_index - 1]
        except Exception:
            pass
    
    st.write("### Preview of Cleaned Data:")
    st.dataframe(df_cleaned.head(10))

    # Provide a download button for the cleaned Excel file
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

# Store the cleaned DataFrame in session state if it exists
if df_cleaned is not None:
    st.session_state.df_cleaned = df_cleaned

# ---------------------------
# 2) AI Chat Assistant Section
# ---------------------------
st.markdown("---")
st.markdown("## 2) Chat with the AI Assistant")

user_input = st.text_input("Ask me anything about Average Days to Enter Time:")

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
    # Append user question to conversation
    st.session_state.conversation.append({"role": "user", "content": user_input})

    # If user question is a projection-type question
    if any(trigger in user_input.lower() for trigger in projection_triggers):
        if 'df_cleaned' not in st.session_state or st.session_state.df_cleaned is None:
            # No file cleaned yet
            warning_msg = "Please upload an Excel file above to calculate your projection."
            st.warning(warning_msg)
            assistant_reply = warning_msg
            st.session_state.conversation.append({"role": "assistant", "content": assistant_reply})
        else:
            # Show projection input form
            st.markdown("**To calculate your projection, please provide the following details:**")
            title = st.text_input("Enter your Title:")
            current_date = st.date_input("Current Date:", value=datetime.today())
            current_avg = st.number_input("Current Average Days to Enter Time:", min_value=0.0, value=16.0, step=0.1)
            
            entry_delay = st.number_input(
                "When are you going to enter the time? Enter 0 for the same day, for the next day please enter 1. (entry delay)", 
                min_value=0.0, 
                value=1.0, 
                step=0.1
            )
            
            promised_hours = st.number_input("Hours entered per session:", min_value=0.0, value=7.5, step=0.5)

            if st.button("Calculate Projection"):
                df_cleaned = st.session_state.df_cleaned
                if "Weighted Date Diff" in df_cleaned.columns and "Hours Worked" in df_cleaned.columns:
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

                # Calculate projection
                results = calculate_required_days(
                    current_weighted_date_diff,
                    current_hours_worked,
                    promised_hours,
                    entry_delay
                )
                target_date = current_date + timedelta(days=results['Required Days'])
                upcoming_reset = get_upcoming_reset_date(title, current_date)

                # Format the dates as MM/DD/YYYY
                target_date_str = target_date.strftime('%m/%d/%Y')
                upcoming_reset_str = upcoming_reset.strftime('%m/%d/%Y')

                # Build single final GPT response
                disclaimer = knowledge_base.get("disclaimers", {}).get("primary_disclaimer", "")
                projection_message = (
                    f"{disclaimer}\n\n"
                    f"Projection Results:\n"
                    f"- **Current Average:** {results['Current Average']:.2f} days\n"
                    f"- **Projected Average:** {results['Projected Average']:.2f} days\n"
                    f"- **Required Additional Days:** {results['Required Days']}\n"
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
        # Normal Q&A from knowledge base
        assistant_reply = find_best_answer(user_input, qna_pairs)
        st.session_state.conversation.append({"role": "assistant", "content": assistant_reply})

# Display Only GPT's Latest Answer
latest_gpt_answer = None
for msg in reversed(st.session_state.conversation):
    if msg["role"] == "assistant":
        latest_gpt_answer = msg["content"]
        break

if latest_gpt_answer:
    st.markdown(f"**GPT:** {latest_gpt_answer}")

# ---------------------------
# Conversation History (Collapsed by Default)
# ---------------------------
with st.expander("Show Full Conversation History", expanded=False):
    for msg in st.session_state.conversation:
        role_label = "GPT" if msg["role"] == "assistant" else "You"
        st.markdown(f"**{role_label}:** {msg['content']}")

# ---------------------------
# Clear Conversation Button
# ---------------------------
st.markdown("---")
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
