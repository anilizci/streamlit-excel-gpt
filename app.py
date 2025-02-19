import streamlit as st
import pandas as pd
import io
import os
import json
import difflib
import openai
from datetime import datetime, timedelta

# ---------------------------
# Page Config & Custom Styling
# ---------------------------
st.set_page_config(
    page_title="Average Days to Enter Time - AI Assistant",
    page_icon=":bar_chart:",
    layout="wide"
)

# Custom CSS to hide Streamlit branding, style buttons, etc.
st.markdown(
    """
    <style>
    /* Hide Streamlit menu & footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Off-white background for a refined look */
    .main {
        background-color: #F7F7F7;
        padding: 20px;
    }

    /* Style the sidebar background */
    section[data-testid="stSidebar"] {
        background-color: #ECECEC;
    }

    /* Make the sidebar menu items bigger */
    section[data-testid="stSidebar"] button {
        font-size: 1.2rem !important;
        font-weight: 600;
        height: 3rem;
        margin-bottom: 0.5rem;
        border-radius: 6px;
        border: none;
        background-color: #0A5A9C;
        color: white;
    }
    section[data-testid="stSidebar"] button:hover {
        background-color: #08426f; /* Darker hover color */
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

if 'selected_menu' not in st.session_state:
    st.session_state.selected_menu = "chatbot"  # Default to Chat Bot

# ---------------------------
# Securely Get API Key
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
        st.error("knowledge_base.json not found! Ensure it's in the project folder.")
        return {}

knowledge_base = load_knowledge_base()

# ---------------------------
# Extract Q&A Pairs
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
# Sidebar Menu (Buttons)
# ---------------------------
st.sidebar.title("Menu")
if st.sidebar.button("Average Days to Enter Time - Chat Bot"):
    st.session_state.selected_menu = "chatbot"
if st.sidebar.button("General Suggestions"):
    st.session_state.selected_menu = "general"

# ---------------------------
# MAIN CONTENT
# ---------------------------
st.title("Average Days to Enter Time - AI Assistant")

# If "General Suggestions" is selected
if st.session_state.selected_menu == "general":
    st.markdown("## General Suggestions")
    st.write("Use this area for general best practices, tips, or suggestions about time entry.")
    st.info("Placeholder for general suggestions content.")

# Otherwise, "Average Days to Enter Time - Chat Bot"
else:
    st.markdown("## Chat with the AI Assistant")

    user_input = st.text_input("Ask me anything about Average Days to Enter Time:")

    if user_input:
        # Show a "thinking" spinner
        with st.spinner("Thinking..."):
            st.session_state.conversation.append({"role": "user", "content": user_input})
            # Normal Q&A from knowledge base
            assistant_reply = find_best_answer(user_input, qna_pairs)
            st.session_state.conversation.append({"role": "assistant", "content": assistant_reply})

    # Display only the latest GPT answer
    latest_gpt_answer = None
    for msg in reversed(st.session_state.conversation):
        if msg["role"] == "assistant":
            latest_gpt_answer = msg["content"]
            break

    if latest_gpt_answer:
        st.markdown(f"**GPT:** {latest_gpt_answer}")

# ---------------------------
# Conversation History
# ---------------------------
with st.expander("Show Full Conversation History", expanded=False):
    for msg in st.session_state.conversation:
        role_label = "GPT" if msg["role"] == "assistant" else "You"
        st.markdown(f"**{role_label}:** {msg['content']}")

# ---------------------------
# Clear Conversation
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
