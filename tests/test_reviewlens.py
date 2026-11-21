import pytest
from pydantic import ValidationError
from unittest.mock import MagicMock, patch
from services.cleaner import parse_and_clean_csv
from services.analyzer import (
    ReviewAnalysisSchema,
    _parse_and_validate_batch,
    _call_gemini_with_backoff,
)


def test_csv_cleaning_and_deduplication():
    raw_csv = (
        "review_id,product,rating,review_text\n"
        "R001,Earbuds,five,<b>Great sound!</b>\n"
        "R002,Earbuds,5,Great sound!\n"
        "R003,Earbuds,,   \n"
    ).encode("utf-8")

    result = parse_and_clean_csv(raw_csv)
    rows = result["rows"]
    stats = result["stats"]

    assert len(rows) == 3
    assert rows[0]["rating"] == 5
    assert rows[0]["review_text"] == "Great sound!"
    assert rows[0]["text_hash"] == rows[1]["text_hash"]
    assert rows[2]["status"] == "skipped_empty"
    assert rows[2]["rating"] == "unknown"
    assert isinstance(stats, dict) and len(stats) > 0


def test_pydantic_schema_validation_and_injection_guard():
    valid_json = """
    [
      {
        "review_id": "R012",
        "sentiment": "negative",
        "topics": ["quality"],
        "summary": "Left earbud stopped working after two days.",
        "needs_reply": true
      }
    ]
    """
    parsed = _parse_and_validate_batch(valid_json, ["R012"])
    assert "R012" in parsed
    assert parsed["R012"]["sentiment"] == "negative"
    assert parsed["R012"]["needs_reply"] is True

    with pytest.raises(ValidationError):
        ReviewAnalysisSchema(
            review_id="R999",
            sentiment="super_positive",
            topics=["quality"],
            summary="Invalid sentiment label.",
            needs_reply=False,
        )


@patch("services.analyzer.time.sleep", return_value=None)
@patch("services.analyzer._get_client")
def test_gemini_retry_and_fallback_logic(mock_get_client, mock_sleep):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    success_response = MagicMock()
    success_response.text = '[{"review_id": "R001", "sentiment": "positive", "topics": ["quality"], "summary": "Good.", "needs_reply": false}]'

    mock_client.models.generate_content.side_effect = [
        RuntimeError("503 UNAVAILABLE: Service temporarily overloaded"),
        success_response,
    ]

    output = _call_gemini_with_backoff("Test prompt", max_retries=2)
    assert "R001" in output
    assert mock_client.models.generate_content.call_count == 2
    mock_sleep.assert_called_once()