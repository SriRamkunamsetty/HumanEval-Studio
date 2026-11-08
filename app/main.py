from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse

from app.models import ReviewSubmission
from app.rlhf_export import to_dpo_pair, to_jsonl_dataset, to_markdown_audit_report
from app.scoring import calculate_scorecard

app = FastAPI(
    title="HumanEval Studio",
    description="Interactive multi-turn conversation review and RLHF annotation platform.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WEB_DIR = Path(__file__).parent / "web"
BENCHMARK_PATH = Path(__file__).parents[1] / "benchmarks" / "rlhf_dialogues.json"

# In-memory storage for submitted reviews
REVIEWS_STORE: dict[str, ReviewSubmission] = {}


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok", "service": "humaneval-studio"}


@app.get("/benchmarks")
def get_benchmarks():
    if not BENCHMARK_PATH.exists():
        return []
    import json
    return json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))


@app.post("/api/reviews", status_code=201)
def submit_review(submission: ReviewSubmission):
    REVIEWS_STORE[submission.dialogue_id] = submission
    scorecard = calculate_scorecard(submission)
    return {
        "status": "success",
        "dialogue_id": submission.dialogue_id,
        "scorecard": scorecard,
    }


@app.get("/api/reviews")
def list_reviews():
    return [
        {
            "dialogue_id": s.dialogue_id,
            "title": s.title,
            "overall_rating": s.overall_rating,
            "failure_tags": [t.value for t in s.failure_tags],
            "created_at": s.created_at,
            "quality_tier": calculate_scorecard(s)["quality_tier"],
        }
        for s in REVIEWS_STORE.values()
    ]


@app.get("/api/reviews/{dialogue_id}")
def get_review(dialogue_id: str):
    sub = REVIEWS_STORE.get(dialogue_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Review session not found")
    return {
        "submission": sub,
        "scorecard": calculate_scorecard(sub),
    }


@app.get("/api/reviews/{dialogue_id}/report")
def get_markdown_report(dialogue_id: str):
    sub = REVIEWS_STORE.get(dialogue_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Review session not found")
    report = to_markdown_audit_report(sub)
    return PlainTextResponse(report, media_type="text/markdown")


@app.get("/api/reviews/{dialogue_id}/dpo")
def get_dpo(dialogue_id: str):
    sub = REVIEWS_STORE.get(dialogue_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Review session not found")
    return to_dpo_pair(sub)


@app.get("/api/export/jsonl")
def export_jsonl():
    content = to_jsonl_dataset(list(REVIEWS_STORE.values()))
    return Response(
        content=content,
        media_type="application/x-jsonlines",
        headers={"Content-Disposition": "attachment; filename=humaneval-rlhf-dataset.jsonl"},
    )


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/app.js", include_in_schema=False)
def javascript():
    return FileResponse(WEB_DIR / "app.js", media_type="text/javascript")


@app.get("/style.css", include_in_schema=False)
def stylesheet():
    return FileResponse(WEB_DIR / "style.css", media_type="text/css")
