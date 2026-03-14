"""Flask app: chat UI with RAG chat and answer feedback."""
from datetime import datetime, timezone

from flask import Flask, render_template, request, jsonify

from rag.feedback import record_feedback
from rag.retriever import query, _get_index

app = Flask(__name__)

# Pre-load the embedding model at startup so the first chat request is fast.
try:
    _get_index()
except Exception:
    pass  # index not built yet; fails silently until /reindex is run


def _run_slash_command(message: str, role: str) -> dict:
    """Handle slash commands from chat input."""
    command = (message or "").strip().lower()
    if command in {"/help", "/?"}:
        return {
            "response": (
                "Available slash commands:\n"
                "- /help: show this list\n"
                "- /reindex: rebuild vectors from company documents"
            ),
            "images": [],
        }
    if command == "/reindex":
        started_at = datetime.now(timezone.utc)
        # Lazy import keeps app startup light for deployment health checks.
        from rag.ingestion import run_ingestion

        run_ingestion()
        return {
            "response": (
                "Reindex complete.\n"
                f"- role: {role}\n"
                f"- started_at: {started_at.isoformat()}"
            ),
            "images": [],
        }
    return {
        "response": "Unknown slash command. Try /help.",
        "images": [],
    }


@app.route("/")
def index():
    """Serve the chat page with role selector."""
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    """Handle a chat message: run RAG and return the assistant reply."""
    try:
        body = request.get_json() or {}
        message = (body.get("message") or "").strip()
        role = (body.get("role") or "patient").lower()
        history = body.get("history") or []
        if role not in ("patient", "staff"):
            role = "patient"

        if not message:
            return jsonify({"response": "Please enter a question."}), 400

        if message.startswith("/"):
            slash_result = _run_slash_command(message, role)
            return jsonify(slash_result)

        rag_result = query(
            question=message,
            role=role,
            history=history if isinstance(history, list) else [],
        )
        return jsonify(
            {
                "response": rag_result.get("text", ""),
                "images": rag_result.get("images", []),
            }
        )
    except ValueError as e:
        return jsonify({"response": str(e)}), 500
    except Exception as e:
        return jsonify({"response": f"An error occurred: {e}"}), 500


@app.route("/feedback", methods=["POST"])
def feedback():
    """Capture thumbs up/down and persist for future retrieval guidance."""
    try:
        body = request.get_json() or {}
        question = (body.get("question") or "").strip()
        answer = (body.get("answer") or "").strip()
        role = (body.get("role") or "patient").lower().strip()
        signal = (body.get("feedback") or "").lower().strip()
        images = body.get("images") or []
        if role not in ("patient", "staff"):
            role = "patient"
        if not question or not answer or signal not in ("up", "down"):
            return jsonify({"ok": False, "error": "Invalid feedback payload"}), 400

        record_feedback(
            question=question,
            answer=answer,
            role=role,
            feedback=signal,
            images=images if isinstance(images, list) else [],
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000, use_reloader=False)
