"""Streamlit app for DentalBoutique RAG chatbot — deploy to Streamlit Community Cloud."""
from pathlib import Path

import streamlit as st

from rag.feedback import record_feedback
from rag.retriever import query


def _image_path(url: str) -> Path | None:
    """Convert /static/indexed_images/foo.jpg to local file path for st.image."""
    if not url or not isinstance(url, str):
        return None
    if url.startswith("/static/indexed_images/"):
        return Path("static/indexed_images") / url.split("/")[-1]
    return Path(url) if Path(url).exists() else None

st.set_page_config(page_title="DentalBoutique – Ask a question", layout="centered")

# Sidebar: reindex and status
with st.sidebar:
    st.caption("**Tools**")
    if st.button("🔄 Reindex documents", help="Rebuild vectors from company docs"):
        try:
            from rag.ingestion import run_ingestion
            with st.spinner("Reindexing…"):
                run_ingestion()
            st.success("Reindex complete.")
        except Exception as e:
            st.error(f"Reindex failed: {e}")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "role" not in st.session_state:
    st.session_state.role = "patient"
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


def run_slash_command(cmd: str, role: str) -> tuple[str, list]:
    """Handle /help and /reindex slash commands."""
    cmd = (cmd or "").strip().lower()
    if cmd in {"/help", "/?"}:
        return (
            "**Available slash commands:**\n"
            "- `/help` — show this list\n"
            "- `/reindex` — rebuild vectors from company documents",
            [],
        )
    if cmd == "/reindex":
        try:
            from rag.ingestion import run_ingestion
            run_ingestion()
            return "Reindex complete. Vectors rebuilt from company documents.", []
        except Exception as e:
            return f"Reindex failed: {e}", []
    return "Unknown slash command. Try `/help`.", []


# Header
st.title("DentalBoutique")
st.caption("Ask a question about our services, hours, or policies")

# Role selector
st.session_state.role = st.radio(
    "I am:",
    options=["patient", "staff"],
    horizontal=True,
    index=0 if st.session_state.role == "patient" else 1,
    key="role_radio",
)

# Chat messages
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("images"):
            for img in msg["images"]:
                path = _image_path(img.get("url", ""))
                if path and path.exists():
                    st.image(str(path), use_container_width=True)
        # Feedback buttons only for last assistant message
        if msg.get("feedback_payload") and msg["role"] == "assistant" and i == len(st.session_state.messages) - 1:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col2:
                if st.button("👍 Helpful", key=f"fb_up_{i}"):
                    try:
                        record_feedback(
                            question=msg["feedback_payload"]["question"],
                            answer=msg["feedback_payload"]["answer"],
                            role=msg["feedback_payload"]["role"],
                            feedback="up",
                            images=msg["feedback_payload"].get("images", []),
                        )
                        st.success("Thanks!")
                    except Exception:
                        st.error("Save failed")
            with col3:
                if st.button("👎 Not helpful", key=f"fb_down_{i}"):
                    try:
                        record_feedback(
                            question=msg["feedback_payload"]["question"],
                            answer=msg["feedback_payload"]["answer"],
                            role=msg["feedback_payload"]["role"],
                            feedback="down",
                            images=msg["feedback_payload"].get("images", []),
                        )
                        st.success("Recorded")
                    except Exception:
                        st.error("Save failed")

# Chat input
if prompt := st.chat_input("Type your question…"):
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        if prompt.strip().startswith("/"):
            text, images = run_slash_command(prompt.strip(), st.session_state.role)
            st.markdown(text)
        else:
            try:
                history = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages[:-1]
                    if m["role"] in ("user", "assistant")
                ]
                rag_result = query(
                    question=prompt.strip(),
                    role=st.session_state.role,
                    history=history,
                )
                text = rag_result.get("text", "")
                images = rag_result.get("images", [])
                st.markdown(text)
                for img in images:
                    if img.get("url"):
                        st.image(img["url"], use_container_width=True)
            except ValueError as e:
                if "has not been built" in str(e).lower() or "ingestion" in str(e).lower():
                    text = "Index not built yet. Click **🔄 Reindex documents** in the sidebar first."
                else:
                    text = str(e)
                images = []
                st.warning(text)
            except Exception as e:
                text = f"An error occurred: {e}"
                images = []
                st.error(text)

    st.session_state.messages.append({
        "role": "assistant",
        "content": text,
        "images": images,
        "feedback_payload": {
            "question": prompt.strip(),
            "answer": text,
            "role": st.session_state.role,
            "images": images,
        } if not prompt.strip().startswith("/") else None,
    })
    st.rerun()
