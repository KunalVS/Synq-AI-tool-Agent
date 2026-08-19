"""Synq Streamlit UI for the existing Gemini tool-calling agent."""

from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

from agent import GeminiAgent


load_dotenv()

st.set_page_config(
    page_title="Synq",
    page_icon="S",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.html(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');

    :root {
        --synq-bg: #080B12;
        --synq-panel: #111722;
        --synq-panel-soft: rgba(17, 23, 34, 0.88);
        --synq-secondary: #161D2A;
        --synq-border: rgba(118, 139, 166, 0.18);
        --synq-border-strong: rgba(118, 139, 166, 0.34);
        --synq-text: #F1F5F9;
        --synq-muted: #8B98AA;
        --synq-accent: #00D9FF;
        --synq-violet: #7C5CFF;
        --synq-success: #22C55E;
        --synq-error: #EF4444;
    }

    html,
    body,
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] .main,
    [data-testid="stAppViewContainer"] .main > div,
    [data-testid="stMain"],
    [data-testid="stBottom"] {
        background: var(--synq-bg) !important;
        color: var(--synq-text) !important;
    }

    [data-testid="stAppScrollToBottomContainer"] {
        scroll-behavior: smooth;
    }

    .stApp {
        font-family: 'DM Sans', ui-sans-serif, system-ui, sans-serif;
    }

    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stDecoration"] { display: none; }

    [data-testid="stBottom"] {
        border-top: 1px solid var(--synq-border) !important;
    }

    [data-testid="stBottom"] > div {
        background: transparent !important;
    }

    .block-container {
        max-width: 1120px;
        padding: 3.25rem 2rem 8rem;
    }

    [data-testid="stSidebar"] {
        background: var(--synq-panel);
        border-right: 1px solid var(--synq-border);
    }

    [data-testid="stSidebar"] > div:first-child { padding: 2rem 1.35rem; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: var(--synq-muted);
        line-height: 1.55;
    }

    .synq-sidebar-brand {
        color: var(--synq-text);
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1.55rem;
        font-weight: 700;
        letter-spacing: 0.22em;
        margin-bottom: 0.55rem;
    }

    .synq-sidebar-label {
        color: var(--synq-muted);
        font-size: 0.67rem;
        font-weight: 600;
        letter-spacing: 0.16em;
        text-transform: uppercase;
    }

    .synq-sidebar-label { margin: 1.8rem 0 0.8rem; }

    .synq-tool-list {
        color: var(--synq-text);
        font-size: 0.88rem;
        line-height: 2.05;
    }

    .synq-tool-list span {
        color: var(--synq-accent);
        display: inline-block;
        font-size: 0.7rem;
        margin-right: 0.55rem;
        transform: translateY(-1px);
    }

    .synq-sidebar-status {
        align-items: center;
        color: var(--synq-text);
        display: flex;
        font-size: 0.84rem;
        gap: 0.55rem;
    }

    .synq-sidebar-status-dot {
        background: var(--synq-success);
        border-radius: 50%;
        box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.1);
        height: 7px;
        width: 7px;
    }

    .synq-welcome {
        margin: 2.4rem auto 1.65rem;
        max-width: 760px;
        text-align: center;
    }

    .synq-welcome h1 {
        color: var(--synq-text);
        font-family: 'Space Grotesk', sans-serif;
        font-size: clamp(1.85rem, 3.2vw, 2.45rem);
        font-weight: 600;
        letter-spacing: -0.04em;
        margin: 0;
    }

    .synq-example-card-title {
        color: var(--synq-text);
        font-size: 0.88rem;
        font-weight: 600;
        margin-bottom: 0.3rem;
    }

    .synq-example-card-copy {
        color: var(--synq-muted);
        font-size: 0.78rem;
        line-height: 1.45;
        margin-bottom: 0.8rem;
    }

    [data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--synq-panel);
        border-color: var(--synq-border) !important;
        border-radius: 12px;
    }

    [data-testid="stChatMessage"] {
        background: var(--synq-panel-soft);
        border: 1px solid var(--synq-border);
        border-radius: 16px;
        margin: 0.9rem auto;
        max-width: 900px;
        padding: 1rem 1.15rem;
    }

    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        background: rgba(22, 29, 42, 0.88);
        border-color: rgba(0, 217, 255, 0.16);
    }

    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
        background: var(--synq-panel-soft);
    }

    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p {
        color: var(--synq-text);
        line-height: 1.65;
    }

    [data-testid="stChatMessage"] [data-testid="stChatMessageAvatarUser"],
    [data-testid="stChatMessage"] [data-testid="stChatMessageAvatarAssistant"] {
        background: var(--synq-secondary);
        border: 1px solid var(--synq-border-strong);
        color: var(--synq-accent);
    }

    [data-testid="stChatInput"] {
        background: var(--synq-panel) !important;
        border: 1px solid var(--synq-border-strong);
        border-radius: 11px;
        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.16);
    }

    [data-testid="stChatInput"] [data-baseweb="textarea"],
    [data-testid="stChatInput"] textarea {
        background: transparent !important;
    }

    [data-testid="stChatInput"]:focus-within {
        border-color: rgba(0, 217, 255, 0.58);
        box-shadow: 0 0 0 3px rgba(0, 217, 255, 0.08), 0 12px 30px rgba(124, 92, 255, 0.06);
    }

    [data-testid="stChatInput"] textarea {
        color: var(--synq-text);
        font-size: 0.9rem;
    }

    [data-testid="stChatInput"] button {
        background: var(--synq-accent);
        border-radius: 8px;
        color: #061018;
    }

    [data-testid="stChatInput"] button:hover {
        background: #42E3FF;
        box-shadow: 0 0 14px rgba(0, 217, 255, 0.18);
        color: #061018;
    }

    .stButton > button {
        background: var(--synq-secondary);
        border: 1px solid var(--synq-border);
        border-radius: 10px;
        color: var(--synq-text);
        font-size: 0.79rem;
        min-height: 2.45rem;
        text-align: left;
        transition: border-color 120ms ease, background 120ms ease;
    }

    .stButton > button:hover {
        background: #1B2433;
        border-color: rgba(0, 217, 255, 0.48);
        box-shadow: 0 0 12px rgba(124, 92, 255, 0.08);
        color: var(--synq-text);
    }

    .synq-divider { border-top: 1px solid var(--synq-border); margin: 2.2rem 0 1rem; }

    @media (max-width: 700px) {
        .block-container { padding: 2rem 1rem 7rem; }
        .synq-welcome { margin-top: 1.5rem; }
    }
    </style>
    """,
)


SPINNER_VERBS = (
    "Pondering",
    "Sleuthing",
    "Triangulating",
    "Brewing",
    "Booping",
    "Orchestrating",
    "Ruminating",
    "Crystallizing",
    "Schlepping",
    "Flibbertigibbeting",
)

def get_agent() -> GeminiAgent:
    if "agent" not in st.session_state:
        st.session_state.agent = GeminiAgent(os.getenv("GEMINI_API_KEY", ""))
    return st.session_state.agent


def next_spinner_verb() -> str:
    index = st.session_state.get("spinner_index", 0)
    st.session_state.spinner_index = (index + 1) % len(SPINNER_VERBS)
    return SPINNER_VERBS[index]


def clear_conversation() -> None:
    st.session_state.messages = []
    st.session_state.spinner_index = 0


with st.sidebar:
    st.markdown('<div class="synq-sidebar-brand">Synq</div>', unsafe_allow_html=True)
    st.markdown('<div class="synq-sidebar-label">Tools</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="synq-tool-list">
          <div><span>01</span>Calculator</div>
          <div><span>02</span>Weather</div>
          <div><span>03</span>Text Utility</div>
          <div><span>04</span>Currency Converter</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="synq-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="synq-sidebar-label">Agent status</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="synq-sidebar-status"><span class="synq-sidebar-status-dot"></span>Online</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="synq-divider"></div>', unsafe_allow_html=True)
    if st.button("Clear conversation", use_container_width=True, on_click=clear_conversation):
        st.rerun()


if not os.getenv("GEMINI_API_KEY"):
    st.error("GEMINI_API_KEY is missing. Add it to .env, then reload the app.")
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []

if not st.session_state.messages:
    st.markdown(
        """
        <div class="synq-welcome">
          <h1>What can I help you accomplish?</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )
    example_prompts = (
        ("Calculator", "Calculate 847 × 29"),
        ("Weather", "What's the weather in Pune?"),
        ("Text Utility", "Count the words in this sentence"),
        ("Currency", "Convert 100 USD to INR"),
    )
    for row_start in range(0, len(example_prompts), 2):
        example_columns = st.columns(2, gap="small")
        for column, (title, example) in zip(example_columns, example_prompts[row_start : row_start + 2]):
            with column:
                with st.container(border=True):
                    st.markdown(f'<div class="synq-example-card-title">{title}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="synq-example-card-copy">{example}</div>', unsafe_allow_html=True)
                    if st.button(example, key=f"example_{title}", use_container_width=True):
                        st.session_state.pending_prompt = example
                        st.rerun()
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

pending_prompt = st.session_state.pop("pending_prompt", None)
pending_agent_prompt = st.session_state.pop("pending_agent_prompt", None)
prompt = st.chat_input(
    "Ask Synq anything..."
)
prompt = prompt or pending_prompt

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.pending_agent_prompt = prompt
    st.rerun()

if pending_agent_prompt:
    with st.chat_message("assistant"):
        try:
            with st.spinner(f"{next_spinner_verb()}…"):
                answer = get_agent().run(pending_agent_prompt)
            st.markdown(answer)
        except (RuntimeError, ValueError) as exc:
            answer = f"Agent error: {exc}"
            st.error(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
