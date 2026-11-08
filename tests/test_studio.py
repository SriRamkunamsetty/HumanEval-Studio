from fastapi.testclient import TestClient

from app.main import REVIEWS_STORE, app
from app.models import ChatMessage, FailureCategory, ReviewSubmission, Role, RubricDimensionScore
from app.scoring import calculate_scorecard

client = TestClient(app)


def setup_function():
    REVIEWS_STORE.clear()


def sample_submission(tags=None) -> ReviewSubmission:
    return ReviewSubmission(
        dialogue_id="test-dial-001",
        title="Sample Test Dialogue",
        conversation=[
            ChatMessage(role=Role.USER, content="What is the capital of France?", turn_index=0),
            ChatMessage(role=Role.ASSISTANT, content="The capital of France is Paris.", turn_index=1),
        ],
        scores=[
            RubricDimensionScore(dimension="helpfulness", score=5, rationale="Direct answer"),
            RubricDimensionScore(dimension="accuracy", score=5, rationale="Accurate fact"),
        ],
        failure_tags=tags or [],
        overall_rating=5,
        reviewer_notes="Great concise response.",
        reviewer_id="tester-01",
    )


def test_scorecard_calculation_clean():
    sub = sample_submission()
    card = calculate_scorecard(sub)
    assert card["raw_average_score"] == 5.0
    assert card["adjusted_quality_score"] == 5.0
    assert card["quality_tier"] == "HIGH_QUALITY_GOLD"
    assert card["is_ready_for_training"] is True


def test_scorecard_calculation_penalties():
    sub = sample_submission(tags=[FailureCategory.HALLUCINATION, FailureCategory.INSTRUCTION_VIOLATION])
    card = calculate_scorecard(sub)
    assert card["raw_average_score"] == 5.0
    # Penalty: 1.5 (hallucination) + 1.0 (instruction_violation) = 2.5
    assert card["adjusted_quality_score"] == 2.5
    assert card["quality_tier"] == "NEEDS_REVISION"
    assert card["is_ready_for_training"] is False


def test_submit_review_api():
    payload = sample_submission().model_dump(mode="json")
    response = client.post("/api/reviews", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["scorecard"]["quality_tier"] == "HIGH_QUALITY_GOLD"

    # Verify listing
    res_list = client.get("/api/reviews")
    assert res_list.status_code == 200
    assert len(res_list.json()) == 1


def test_markdown_report_and_dpo_endpoints():
    sub = sample_submission()
    client.post("/api/reviews", json=sub.model_dump(mode="json"))

    # Test report
    report_res = client.get(f"/api/reviews/{sub.dialogue_id}/report")
    assert report_res.status_code == 200
    assert "Dialogue Transcript" in report_res.text
    assert "Paris" in report_res.text

    # Test DPO
    dpo_res = client.get(f"/api/reviews/{sub.dialogue_id}/dpo")
    assert dpo_res.status_code == 200
    assert dpo_res.json()["prompt"] == "What is the capital of France?"


def test_export_jsonl():
    sub = sample_submission()
    client.post("/api/reviews", json=sub.model_dump(mode="json"))
    export_res = client.get("/api/export/jsonl")
    assert export_res.status_code == 200
    assert "test-dial-001" in export_res.text


def test_get_benchmarks():
    response = client.get("/benchmarks")
    assert response.status_code == 200
    benchmarks = response.json()
    assert len(benchmarks) >= 3
    assert any(bm["benchmark_id"] == "BM-MED-001" for bm in benchmarks)
