import streamlit as st
import pandas as pd

# App title
st.title("Excel File Cleaner & GPT Assistant")

# File upload
uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file, engine='openpyxl')
    st.write("Preview of Uploaded Data:", df.head())

    # Example: Drop first 2 metadata rows
    df_cleaned = df.iloc[2:].reset_index(drop=True)

    st.write("Preview of Cleaned Data:", df_cleaned.head())

    # Download cleaned file
    st.download_button("Download Cleaned Excel", df_cleaned.to_csv(index=False).encode(), "cleaned_data.csv", "text/csv")
