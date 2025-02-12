import streamlit as st
import pandas as pd

# App title
st.title("Excel File Cleaner & GPT Assistant")

# File upload
uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file, engine='openpyxl')

    st.write("Preview of Uploaded Data:", df.head())

    # Remove metadata rows dynamically
    df = df.iloc[1:].reset_index(drop=True)  # Drops the first row

    # Assign proper column headers
    df.columns = df.iloc[0]  # Set second row as headers
    df = df[1:].reset_index(drop=True)

    # Drop empty and unnamed columns
    df = df.dropna(axis=1, how='all')  # Drop fully empty columns
    df = df.loc[:, ~df.columns.astype(str).str.contains('Unnamed', na=False)]

    # Drop fully empty rows
    df.dropna(how='all', inplace=True)

    st.write("Preview of Cleaned Data:", df.head())

    # Download cleaned file
    st.download_button("Download Cleaned Excel", df.to_csv(index=False).encode(), "cleaned_data.csv", "text/csv")
