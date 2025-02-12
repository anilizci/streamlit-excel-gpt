import streamlit as st
import pandas as pd

# App title
st.title("Excel File Cleaner & GPT Assistant")

# File upload
uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file, engine='openpyxl')

    st.write("Preview of Uploaded Data (Before Cleaning):", df.head())

    # Step 1: Remove metadata rows (first row)
    df = df.iloc[1:].reset_index(drop=True)

    # Step 2: Set the second row as column headers
    df.columns = df.iloc[0].fillna("Unnamed")  # Replace NaN headers
    df = df[1:].reset_index(drop=True)

    # Step 3: Remove completely empty columns
    df = df.dropna(axis=1, how='all')

    # Step 4: Remove columns with 'Unnamed' in their names
    df = df.loc[:, ~df.columns.astype(str).str.contains('Unnamed', na=False)]

    # Step 5: Remove fully empty rows
    df.dropna(how='all', inplace=True)

    # Step 6: Reset the index again
    df.reset_index(drop=True, inplace=True)

    st.write("Preview of Cleaned Data:", df.head())

    # Allow downloading the cleaned file
    st.download_button("Download Cleaned Excel", df.to_csv(index=False).encode(), "cleaned_data.csv", "text/csv")
