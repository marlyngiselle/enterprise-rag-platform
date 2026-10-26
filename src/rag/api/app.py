"""HTTP API.

``POST /v1/ask`` returns a grounded answer with citations. ``POST /v1/ask/stream`` returns
server sent events: ``sources``, then ``token`` events, then ``done`` with the verdict.
Every response carries ``x-request-id``, which is also set on the active span.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Awaitable, Callable, Iterator
from contextvars import ContextVar

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from opentelemetry import trace
from pydantic import BaseModel, Field

from rag import __version__
from rag.api.auth import resolve_principal
from rag.api.telemetry import configure_telemetry
from rag.config import Settings
from rag.factory import Components, build_components
from rag.generation.service import citation_payload
from rag.models import Principal

REQUEST_ID_HEADER = "x-request-id"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4000)


class CitationOut(BaseModel):
    marker: int
    source: str
    title: str
    section: str


class AskResponse(BaseModel):
    answer: str
    citations: list[CitationOut]
    refused: bool
    refusal_reason: str | None
    request_id: str


def _sse(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def create_app(settings: Settings | None = None, components: Components | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Enterprise RAG API", version=__version__)
    app.state.settings = settings
    app.state.components = components or build_components(settings)
    app.state.exporter = configure_telemetry(app)

    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming if _SAFE_REQUEST_ID.fullmatch(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        trace.get_current_span().set_attribute("request.id", request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    def principal(request: Request) -> Principal:
        return resolve_principal(request, settings.auth_mode)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "backend": settings.backend, "version": __version__}

    @app.post("/v1/ask", response_model=AskResponse)
    def ask(body: AskRequest, caller: Principal = Depends(principal)) -> AskResponse:  # noqa: B008
        trace.get_current_span().set_attribute("request.id", request_id_var.get())
        answer = app.state.components.service.answer(body.question, caller)
        return AskResponse(
            answer=answer.text,
            citations=[CitationOut.model_validate(c) for c in citation_payload(answer.citations)],
            refused=answer.refused,
            refusal_reason=answer.refusal_reason,
            request_id=request_id_var.get(),
        )

    @app.post("/v1/ask/stream")
    def ask_stream(
        body: AskRequest,
        caller: Principal = Depends(principal),  # noqa: B008
    ) -> StreamingResponse:
        service = app.state.components.service
        request_id = request_id_var.get()

        def events() -> Iterator[str]:
            yield _sse("meta", {"request_id": request_id})
            for event in service.stream(body.question, caller):
                yield _sse(event.event, event.data)

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"cache-control": "no-store", "x-accel-buffering": "no"},
        )

    return app


def app_factory() -> FastAPI:
    """Entry point for ``uvicorn --factory rag.api.app:app_factory``."""
    return create_app()
