import os
from collections import Counter
from typing import Any, Dict, List
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from services.analyzer import analyze_reviews, generate_suggested_reply
from services.cache import init_db
from services.cleaner import parse_and_clean_csv

load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB limit
init_db()


def _build_dashboard_summary(reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
    completed = [r for r in reviews if r.get("analysis_status") == "completed"]
    total = len(completed)

    pos = sum(1 for r in completed if r.get("sentiment") == "positive")
    neu = sum(1 for r in completed if r.get("sentiment") == "neutral")
    neg = sum(1 for r in completed if r.get("sentiment") == "negative")
    needs_reply = sum(1 for r in completed if r.get("needs_reply"))

    rated = [r for r in completed if isinstance(r.get("rating"), int)]
    mismatches = sum(1 for r in rated if r.get("rating_mismatch"))
    agreement_pct = round(((len(rated) - mismatches) / len(rated)) * 100, 1) if rated else 100.0

    neg_topics = Counter()
    pos_topics = Counter()
    for r in completed:
        if r.get("sentiment") == "negative":
            for t in r.get("topics", []):
                neg_topics[t] += 1
        elif r.get("sentiment") == "positive":
            for t in r.get("topics", []):
                pos_topics[t] += 1

    top_complaints = [
        f"{topic.replace('_', ' ').title()} ({count} mentions)"
        for topic, count in neg_topics.most_common(3)
    ]
    top_praises = [
        f"{topic.replace('_', ' ').title()} ({count} mentions)"
        for topic, count in pos_topics.most_common(3)
    ]

    # Bonus: Product-level breakdown
    products_map: Dict[str, Dict[str, Any]] = {}
    for r in completed:
        prod = r.get("product", "Unknown")
        if prod not in products_map:
            products_map[prod] = {"product": prod, "total": 0, "positive": 0, "neutral": 0, "negative": 0, "neg_topics": Counter()}
        products_map[prod]["total"] += 1
        sent = r.get("sentiment", "neutral")
        products_map[prod][sent] += 1
        if sent == "negative":
            for t in r.get("topics", []):
                products_map[prod]["neg_topics"][t] += 1

    product_cards = []
    for prod, info in products_map.items():
        top_issue = info["neg_topics"].most_common(1)
        product_cards.append({
            "product": prod,
            "total": info["total"],
            "positive": info["positive"],
            "neutral": info["neutral"],
            "negative": info["negative"],
            "top_issue": f"{top_issue[0][0].replace('_', ' ').title()} ({top_issue[0][1]})" if top_issue else "None",
        })

    return {
        "total_analysed": total,
        "positive_pct": round((pos / total) * 100, 1) if total else 0.0,
        "neutral_pct": round((neu / total) * 100, 1) if total else 0.0,
        "negative_pct": round((neg / total) * 100, 1) if total else 0.0,
        "needs_reply_count": needs_reply,
        "mismatch_count": mismatches,
        "rating_agreement_pct": agreement_pct,
        "top_complaints": top_complaints,
        "top_praises": top_praises,
        "product_breakdown": product_cards,
    }


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    if "file" not in request.files:
        return jsonify({"error": "No CSV file uploaded."}), 400

    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith(".csv"):
        return jsonify({"error": "Please upload a valid .csv file."}), 400

    try:
        cleaned = parse_and_clean_csv(file.read())
        analysis_output = analyze_reviews(cleaned["rows"], batch_size=5)
        summary = _build_dashboard_summary(analysis_output["reviews"])

        return jsonify({
            "summary": summary,
            "cleaning_stats": cleaned["stats"],
            "reviews": analysis_output["reviews"],
            "meta": analysis_output["meta"],
        })
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as exc:
        return jsonify({"error": f"Server error: {str(exc)}"}), 500


@app.route("/api/generate-reply", methods=["POST"])
def api_generate_reply():
    payload = request.get_json(silent=True) or {}
    product = str(payload.get("product") or "").strip()
    rating = payload.get("rating", "unknown")
    review_text = str(payload.get("review_text") or "").strip()
    summary = str(payload.get("summary") or "").strip()

    if not review_text:
        return jsonify({"error": "Review text is required."}), 400

    try:
        reply = generate_suggested_reply(product, rating, review_text, summary)
        return jsonify({"reply": reply})
    except Exception as exc:
        return jsonify({"error": f"Failed to generate reply: {str(exc)}"}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)