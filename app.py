       padding: 20px;
   }

    /* Style the tabs to look more refined */
    .stTabs [data-baseweb="tab"] {
        font-size: 1.1rem;
        font-weight: 500;
        color: #0A5A9C;  /* Corporate-like navy color */
    }

   /* Style primary buttons (e.g., 'Calculate Projection') */
   .stButton>button {
        background-color: #0A5A9C;
        background-color: #0A5A9C; /* Corporate-like navy color */
       color: white;
       border-radius: 6px;
       padding: 0.6rem 1.2rem;
@@ -59,7 +52,7 @@
       border: none;
   }

    /* Style the expander for conversation history */
    /* Style the expander header for conversation history */
   .streamlit-expanderHeader {
       font-size: 1rem;
       font-weight: 600;
@@ -171,178 +164,189 @@ def get_upcoming_reset_date(title, current_date):
return datetime(year + 1, reset_month, reset_day).date()

# ---------------------------
# TABS for Organization
# Main Page Title
# ---------------------------
tabs = st.tabs(["File Upload & Cleaning", "AI Chat Assistant"])
st.title("Average Days to Enter Time - AI Assistant")

with tabs[0]:
    st.markdown("## File Upload & Cleaning")
    uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx"])
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

    # Provide a placeholder for the cleaned DataFrame (session-level).
    if 'df_cleaned' not in st.session_state:
        st.session_state.df_cleaned = None

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

        # Store cleaned DataFrame in session state for use in the chat
        st.session_state.df_cleaned = df_cleaned

        # Provide a download button for the cleaned Excel file.
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

with tabs[1]:
    st.markdown("## AI Chat Assistant")

    user_input = st.text_input("Ask me anything about Average Days to Enter Time:")
    projection_triggers = [
        "lower my average", 
        "reduce my average", 
        "decrease my average", 
        "how long to get under 5", 
        "how to lower my average", 
        "my average days"
    ]
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

    if user_input:
        # Append user question to conversation
        st.session_state.conversation.append({"role": "user", "content": user_input})

        # Check if user question is projection-type
        if any(trigger in user_input.lower() for trigger in projection_triggers):
            if st.session_state.df_cleaned is None:
                warning_msg = "Please upload an Excel file to calculate your projection (in the 'File Upload & Cleaning' tab)."
                st.warning(warning_msg)
                assistant_reply = warning_msg
                st.session_state.conversation.append({"role": "assistant", "content": assistant_reply})
            else:
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
                    # Attempt to extract values from the session-stored DataFrame
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

                    # Calculate projection
                    results = calculate_required_days(
                        current_weighted_date_diff,
                        current_hours_worked,
                        promised_hours,
                        entry_delay
                    )
                    target_date = current_date + timedelta(days=results['Required Days'])
                    upcoming_reset = get_upcoming_reset_date(title, current_date)

                    # Format dates as MM/DD/YYYY
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
                if target_date > upcoming_reset:
                    projection_message += (
                        f"\n**Note:** With your current working schedule, the projected date "
                        f"({target_date_str}) falls after your title's reset date "
                        f"({upcoming_reset_str}). "
                        "This means the projection may not be achievable as calculated. "
                        "Consider increasing your entry frequency or hours."
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

                    # Store final GPT answer in conversation
                    st.session_state.conversation.append({"role": "assistant", "content": projection_message})
    else:
        # Normal Q&A from knowledge base
        assistant_reply = find_best_answer(user_input, qna_pairs)
        st.session_state.conversation.append({"role": "assistant", "content": assistant_reply})

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

    # Display Only GPT's Latest Answer
    latest_gpt_answer = None
    for msg in reversed(st.session_state.conversation):
        if msg["role"] == "assistant":
            latest_gpt_answer = msg["content"]
            break

    if latest_gpt_answer:
        st.markdown(f"**GPT:** {latest_gpt_answer}")

    # Conversation History (Collapsed by Default)
    with st.expander("Show Full Conversation History", expanded=False):
        for msg in st.session_state.conversation:
            role_label = "GPT" if msg["role"] == "assistant" else "You"
            st.markdown(f"**{role_label}:** {msg['content']}")

    # Clear Conversation Button
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
