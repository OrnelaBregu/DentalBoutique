"""Flask app: chat UI with RAG chat and answer feedback."""

from flask import Flask, render_template, request, jsonify

from rag.feedback import record_feedback
from rag.retriever import query

app = Flask(__name__)


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
        if role not in ("patient", "staff"):
            role = "patient"

        if not message:
            return jsonify({"response": "Please enter a question."}), 400

        rag_result = query(question=message, role=role)
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
    app.run(debug=True, port=5000)
