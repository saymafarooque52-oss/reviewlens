from collections import Counter
from flask import Flask, jsonify, render_template, request

from services.analyzer import analyze_reviews, generate_suggested_reply
from services.cleaner import parse_and_clean_csv

app = Flask(__name__)


def _build_dashboard_summary(enriched_reviews: list) -> dict:
    completed = [r for r in enriched_reviews if r.get("analysis_status") == "completed"]
    total_analysed = len(completed)

    pos = sum(1 for r in completed if r["sentiment"] == "positive")
    neu = sum(1 for r in completed if r["sentiment"] == "neutral")
    neg = sum(1 for r in completed if r["sentiment"] == "negative")
    needs_reply_count = sum(1 for r in completed if r["needs_reply"])

    pct_pos = round((pos / total_analysed) * 100, 1) if total_analysed else 0
    pct_neu = round((neu / total_analysed) * 100, 1) if total_analysed else 0
    pct_neg = round((neg / total_analysed) * 100, 1) if total_analysed else 0

    # Aggregate top 3 complaints & praises from analyzed summaries/topics
    neg_reviews = [r for r in completed if r["sentiment"] == "negative"]
    pos_reviews = [r for r in completed if r["sentiment"] == "positive"]

    neg_topics = Counter(t for r in neg_reviews for t in r.get("topics", []))
    pos_topics = Counter(t for r in pos_reviews for t in r.get("topics", []))

    top_complaints = [
        f"{topic.replace('_', ' ').title()} ({count} mentions): "
        + next((r["summary"] for r in neg_reviews if topic in r["topics"]), "")
        for topic, count in neg_topics.most_common(3)
    ]
    top_praises = [
        f"{topic.replace('_', ' ').title()} ({count} mentions): "
        + next((r["summary"] for r in pos_reviews if topic in r["topics"]), "")
        for topic, count in pos_topics.most_common(3)
    ]

    # Bonus: rating vs sentiment agreement %
    with_numeric_rating = [r for r in completed if isinstance(r.get("rating"), int)]
    mismatches = sum(1 for r in with_numeric_rating if r.get("rating_mismatch"))
    agreement_pct = (
        round(((len(with_numeric_rating) - mismatches) / len(with_numeric_rating)) * 100, 1)
        if with_numeric_rating
        else 100.0
    )

    return {
        "total_analysed": total_analysed,
        "positive_pct": pct_pos,
        "neutral_pct": pct_neu,
        "negative_pct": pct_neg,
        "needs_reply_count": needs_reply_count,
        "top_complaints": top_complaints,
        "top_praises": top_praises,
        "rating_agreement_pct": agreement_pct,
        "mismatch_count": mismatches,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    if "file" not in request.files:
        return jsonify({"error": "No CSV file uploaded."}), 400

    uploaded = request.files["file"]
    if not uploaded.filename.lower().endswith(".csv"):
        return jsonify({"error": "Please upload a valid .csv file."}), 400

    raw_text = uploaded.read().decode("utf-8", errors="replace")
    cleaned_data = parse_and_clean_csv(raw_text)
    analysis_output = analyze_reviews(cleaned_data["reviews"])
    summary = _build_dashboard_summary(analysis_output["reviews"])

    return jsonify({
        "summary": summary,
        "cleaning_stats": cleaned_data["stats"],
        "meta": analysis_output["meta"],
        "reviews": analysis_output["reviews"],
    })


@app.route("/api/generate-reply", methods=["POST"])
def api_generate_reply():
    data = request.get_json(silent=True) or {}
    review_text = data.get("review_text", "").strip()
    if not review_text:
        return jsonify({"error": "Review text is required."}), 400

    try:
        reply = generate_suggested_reply(
            product=data.get("product", "Product"),
            rating=data.get("rating", "unknown"),
            review_text=review_text,
            summary=data.get("summary", ""),
        )
        return jsonify({"reply": reply})
    except Exception as exc:
        return jsonify({"error": f"Failed to generate reply: {str(exc)}"}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)