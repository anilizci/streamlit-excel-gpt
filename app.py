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
    st.session_state.conversation.append({"role": "user", "content": user_input})
    
    # Check if the question is a projection-type query
    if any(trigger in user_input.lower() for trigger in projection_triggers):
        # Display the file uploader only for projection queries
        uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx"])
        df_cleaned = None

        if uploaded_file:
            df = pd.read_excel(uploaded_file, engine='openpyxl')
            st.write("### Preview of Uploaded Data:", df.head())
            
            # Clean the data as before
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
            
            # (Optional) Provide a download button for the cleaned Excel file
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
        
        # Only show projection input form if the file has been uploaded
        if uploaded_file:
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
                # Extract values from the DataFrame (or use placeholder values)
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

                # Calculate projection using your function
                results = calculate_required_days(
                    current_weighted_date_diff,
                    current_hours_worked,
                    promised_hours,
                    entry_delay
                )
                target_date = current_date + timedelta(days=results['Required Days'])
                upcoming_reset = get_upcoming_reset_date(title, current_date)
                
                target_date_str = target_date.strftime('%m/%d/%Y')
                upcoming_reset_str = upcoming_reset.strftime('%m/%d/%Y')

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
        # Normal Q&A from your knowledge base if not a projection question
        assistant_reply = find_best_answer(user_input, qna_pairs)
        st.session_state.conversation.append({"role": "assistant", "content": assistant_reply})
