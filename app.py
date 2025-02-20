# ------------------------------------------
# Inject custom CSS
# ------------------------------------------
# 1) Slightly bigger buttons/inputs
# 2) A white vertical line between col1 and col2
st.markdown("""
<style>
/* Make all Streamlit buttons slightly bigger */
@@ -113,32 +111,15 @@ def traverse(obj):
big_knowledge_text = convert_json_to_text(knowledge_base)

# ------------------------------------------
# Our new chunk-based "find_best_answer" function
# with top 2 chunks
# Our chunk-based "find_best_answer" function (top 2 chunks)
# ------------------------------------------
def find_best_answer_chunked(user_query, knowledge_text):
    """
    1) Split the knowledge_text into chunks (~300 words)
    2) Create embeddings
    3) Find the top 2 chunks
    4) Combine them
    5) Ask GPT
    """
if not knowledge_text.strip():
return "I don't have information on that."

    # Split text into chunks
chunks = split_text(knowledge_text, chunk_size=300, overlap=50)

    # Create embeddings
embeddings = create_embeddings_for_chunks(chunks)

    # Find top 2 chunks
top_chunks = find_top_n_chunks(user_query, embeddings, n=2)
    # Merge them into a single string
combined_chunks = "\n\n".join(f"[Score: {score:.3f}] {chunk}" for score, chunk in top_chunks)

    # Pass combined chunks to GPT
answer = ask_gpt(user_query, combined_chunks)
return answer

@@ -178,6 +159,21 @@ def get_upcoming_reset_date(title, current_date):
else:
return datetime(year + 1, reset_month, reset_day).date()

# NEW: Helper to skip weekends
def add_business_days(start_date, days_needed):
    """
    Moves forward 'days_needed' business days (Mon-Fri), skipping weekends.
    Returns the resulting date.
    """
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
@@ -217,12 +213,9 @@ def get_upcoming_reset_date(title, current_date):
"average is high"
]

    # Only proceed if user typed something
if user_input:
        # Record the user query in conversation
st.session_state.conversation.append({"role": "user", "content": user_input})

        # If the user's query is projection-related, show the Excel uploader and projection form.
if any(trigger in user_input.lower() for trigger in projection_triggers):
uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx"])
df_cleaned = None
@@ -274,7 +267,13 @@ def get_upcoming_reset_date(title, current_date):
)

promised_hours = st.number_input("Hours entered per session:", min_value=0.0, value=7.5, step=0.5)
                

                # NEW: Ask if user works only weekdays or also weekends
                weekend_option = st.selectbox(
                    "Will you work only on weekdays or also on weekends?",
                    ["Weekdays only", "Weekdays + weekends"]
                )

if st.button("Calculate Projection"):
if (df_cleaned is not None 
and "Weighted Date Diff" in df_cleaned.columns 
@@ -290,15 +289,25 @@ def get_upcoming_reset_date(title, current_date):
current_weighted_date_diff = current_avg * 100
current_hours_worked = 100

                    # Calculate how many "days" we need in an abstract sense
results = calculate_required_days(
current_weighted_date_diff,
current_hours_worked,
promised_hours,
entry_delay
)
                    target_date = current_date + timedelta(days=results['Required Days'])

                    required_days = results['Required Days']

                    # Convert those "days" to a target date
                    if weekend_option == "Weekdays only":
                        # Skip weekends
                        target_date = add_business_days(current_date, required_days)
                    else:
                        # All calendar days
                        target_date = current_date + timedelta(days=required_days)

upcoming_reset = get_upcoming_reset_date(title, current_date)
                    
target_date_str = target_date.strftime('%m/%d/%Y')
upcoming_reset_str = upcoming_reset.strftime('%m/%d/%Y')

@@ -308,7 +317,7 @@ def get_upcoming_reset_date(title, current_date):
f"Projection Results:\n"
f"- **Current Average:** {results['Current Average']:.2f} days\n"
f"- **Projected Average:** {results['Projected Average']:.2f} days\n"
                        f"- **Required Additional Days:** {results['Required Days']}\n"
                        f"- **Required Additional Days (Working Days):** {required_days}\n"
f"- **Projected Date to Reach Average Below 5:** {target_date_str}\n"
)

@@ -322,6 +331,7 @@ def get_upcoming_reset_date(title, current_date):
)

st.session_state.conversation.append({"role": "assistant", "content": projection_message})

else:
# Normal Q&A from the knowledge base (embedding-based, top 2 chunks)
assistant_reply = find_best_answer_chunked(user_input, big_knowledge_text)
