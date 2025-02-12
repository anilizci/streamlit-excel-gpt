import streamlit as st
import pandas as pd
import io
import openai

# App title
st.title("Excel File Cleaner & GPT Assistant")

# File upload
uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx"])
df_cleaned = None  # Initialize df_cleaned to be used later

if uploaded_file:
    df = pd.read_excel(uploaded_file, engine='openpyxl')
    st.write("Preview of Uploaded Data:", df.head())

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

    st.write("Preview of Cleaned Data:", df_cleaned.head())

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
st.header("Chat with GPT")

user_input = st.text_input("Ask GPT anything:")

if user_input:
    # Call GPT (Replace 'your-openai-api-key' with your actual OpenAI API key)
    openai.api_key = "your-openai-api-key"

    messages = [
        {"role": "system", "content": "You are a helpful assistant trained to answer questions."},
        {"role": "user", "content": user_input}
    ]

    # If Excel data is available, include it in the context
    if df_cleaned is not None:
        messages.append(
            {"role": "system", "content": f"The user has uploaded an Excel file. Here is the first few rows of cleaned data:\n{df_cleaned.head().to_string()}"}
        )

    # Call GPT API and get response
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=messages
    )

    # Extract GPT response safely
    gpt_response = response["choices"][0]["message"]["content"]

    # Display GPT's response
    st.write("GPT's Response:", gpt_response)
