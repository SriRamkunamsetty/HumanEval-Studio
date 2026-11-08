from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class FailureCategory(str, Enum):
    HALLUCINATION = "hallucination"
    SYCOPHANCY = "sycophancy"
    UNNATURAL_TONE = "unnatural_tone"
    INSTRUCTION_VIOLATION = "instruction_violation"
    OVER_REFUSAL = "over_refusal"
    FORMATTING_ERROR = "formatting_error"
    REASONING_ERROR = "reasoning_error"
    UNGROUNDED_ASSERTION = "ungrounded_assertion"


class ChatMessage(BaseModel):
    role: Role
    content: str = Field(min_length=1, max_length=10000)
    turn_index: int = Field(ge=0)


class RubricDimensionScore(BaseModel):
    dimension: str = Field(min_length=2, max_length=40)
    score: int = Field(ge=1, le=5)  # 1 = Unsatisfactory, 5 = Excellent
    rationale: str = Field(default="", max_length=2000)
    evidence_quote: str = Field(default="", max_length=1000)


class ReviewSubmission(BaseModel):
    dialogue_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = Field(default="Conversation Review", max_length=200)
    conversation: list[ChatMessage] = Field(min_length=1, max_length=50)
    scores: list[RubricDimensionScore] = Field(min_length=1, max_length=10)
    failure_tags: list[FailureCategory] = Field(default_factory=list)
    overall_rating: int = Field(ge=1, le=5)
    reviewer_notes: str = Field(default="", max_length=4000)
    reviewer_id: str = Field(default="reviewer-anon", max_length=80)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DPOPairExport(BaseModel):
    prompt: str
    chosen: str
    rejected: str
    feedback_rationale: str
    failure_tag: str
