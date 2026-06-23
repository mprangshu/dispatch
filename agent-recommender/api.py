"""FastAPI backend — a thin HTTP layer over the existing chatbot core.

Phase 7 (PROJECT_HANDOFF_v2.md section 8). This wraps the *unchanged* ``src``
core over HTTP so a browser/Streamlit frontend (Phase 8) can talk to it. The
core stays interface-decoupled by design (PROBLEM_STATEMENT.md section 7), so
this module only imports the public surface and adds no business logic:

* ``POST /chat``   — run a message through ``chatbot.handle`` and return the reply.
* ``GET  /agents`` — list the live catalog (reflects whatever is in ``agents/``).
* ``GET  /health`` — liveness + whether the LLM key is configured.

Run it (from ``agent-recommender/`` with the venv active):

    uvicorn api:app --reload --port 8000

CORS is open to all origins so the frontend can call it from the browser.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src import config, feedback, handle, llm
from src.loader import load_agents

app = FastAPI(
    title="Agent Recommender & Q&A Chatbot API",
    description="HTTP layer over the agent recommender / Q&A chatbot core.",
    version="1.0.0",
)

# Open CORS so the Streamlit/browser frontend can call the API directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's message to the chatbot.")
    use_llm: bool = Field(
        True,
        description="Use the LLM for answer/explanation prose; False forces the "
        "deterministic, grounded path.",
    )


class ChatResponse(BaseModel):
    reply: str


class AgentInfo(BaseModel):
    agent_id: str
    name: str
    domain: str
    autonomy_default: str
    tags: list[str]


class HealthResponse(BaseModel):
    status: str
    llm_available: bool


class FeedbackRequest(BaseModel):
    message: str = Field(..., description="The user's original query.")
    reply: str = Field(..., description="The bot reply being rated.")
    rating: str = Field(..., description='"positive" or "negative".')
    intent: str | None = Field(
        None, description="recommend | info | clarify, if known to the client."
    )


class FeedbackSavedResponse(BaseModel):
    saved: bool


class FeedbackItem(BaseModel):
    timestamp: str
    message: str
    reply: str
    rating: str
    intent: str | None = None


class FeedbackSummaryResponse(BaseModel):
    total: int
    positive: int
    negative: int
    positive_pct: float
    recent: list[FeedbackItem]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """Route a message through the chatbot and return its single reply."""
    return ChatResponse(reply=handle(req.message, use_llm=req.use_llm))


@app.get("/agents", response_model=list[AgentInfo])
def agents() -> list[AgentInfo]:
    """List every agent in the catalog (read live from ``agents/``)."""
    return [
        AgentInfo(
            agent_id=a.agent_id,
            name=a.name,
            domain=a.domain,
            autonomy_default=a.autonomy_default,
            tags=a.tags,
        )
        for a in load_agents(config.AGENTS_DIR)
    ]


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness check plus whether an LLM key is configured."""
    return HealthResponse(status="ok", llm_available=llm.available())


@app.post("/feedback", response_model=FeedbackSavedResponse)
def submit_feedback(req: FeedbackRequest) -> FeedbackSavedResponse:
    """Store one thumbs-up / thumbs-down rating for a reply."""
    entry = feedback.FeedbackEntry(
        timestamp=feedback.now_iso(),
        message=req.message,
        reply=req.reply,
        rating=req.rating,
        intent=req.intent,
    )
    feedback.save_feedback(entry)
    return FeedbackSavedResponse(saved=True)


@app.get("/feedback/summary", response_model=FeedbackSummaryResponse)
def get_feedback_summary() -> FeedbackSummaryResponse:
    """Aggregate ratings: totals, positive %, and the 5 most recent entries."""
    summary = feedback.feedback_summary()
    return FeedbackSummaryResponse(
        total=summary["total"],
        positive=summary["positive"],
        negative=summary["negative"],
        positive_pct=summary["positive_pct"],
        recent=[FeedbackItem(**asdict(e)) for e in summary["recent"]],
    )
