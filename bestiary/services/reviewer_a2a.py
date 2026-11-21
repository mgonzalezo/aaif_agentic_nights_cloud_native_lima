"""Reviewer agent, reachable over A2A. It belongs to "another team".

It receives a unified diff, asks the model (through Open Responses) for a short review,
and returns the review text plus the raw response items as a data part so the game
can show what Open Responses looks like on the wire.

Run:  uv run python -m bestiary.services.reviewer_a2a     (http://127.0.0.1:9999)
"""

from __future__ import annotations

import argparse
import asyncio
import os

import uvicorn
from a2a.helpers import get_message_text, new_data_part, new_message, new_text_part
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from starlette.applications import Starlette

from bestiary.config import settings
from bestiary.llm import detect, output_text, responses

REVIEW_INSTRUCTIONS = (
    "You are a strict but friendly code reviewer for the farolito project. "
    "Repo rules: errors go to stderr, start with 'farolito: ', and a missing config exits with code 2. "
    "Review the diff in at most three short bullet points, then a final line: "
    "'VERDICT: approve' or 'VERDICT: request changes'."
)


def agent_card(public_url: str) -> AgentCard:
    return AgentCard(
        name="Reviewer (team Lighthouse)",
        description="Reviews small Python diffs against the farolito repo rules.",
        version="0.1.0",
        supported_interfaces=[AgentInterface(url=public_url, protocol_binding="JSONRPC", protocol_version="1.0")],
        capabilities=AgentCapabilities(streaming=False),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain", "application/json"],
        skills=[
            AgentSkill(
                id="review-diff",
                name="Review a diff",
                description="Send a unified diff; get a short review and a verdict.",
                tags=["code-review", "python"],
                examples=["diff --git a/farolito/cli.py b/farolito/cli.py ..."],
            )
        ],
    )


class ReviewerExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        diff = get_message_text(context.message)
        found = detect()
        if not found.provider:
            parts = [new_text_part("No model available to review: " + "; ".join(found.notes))]
        else:
            resp = await asyncio.to_thread(
                responses, found.provider, f"Review this diff:\n\n{diff}", instructions=REVIEW_INSTRUCTIONS
            )
            parts = [
                new_text_part(output_text(resp) or "(empty review)"),
                new_data_part({"open_responses_output": resp.get("output", []), "model": found.provider.label()}),
            ]
        await event_queue.enqueue_event(
            new_message(parts, context_id=context.context_id, task_id=context.task_id)
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        return None


def build_app(public_url: str) -> Starlette:
    card = agent_card(public_url)
    handler = DefaultRequestHandler(
        agent_executor=ReviewerExecutor(), task_store=InMemoryTaskStore(), agent_card=card
    )
    return Starlette(routes=create_agent_card_routes(card) + create_jsonrpc_routes(handler, rpc_url="/"))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="A2A reviewer agent")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=settings().reviewer_port)
    args = parser.parse_args(argv)
    public = os.environ.get("BESTIARY_REVIEWER_PUBLIC_URL", f"http://127.0.0.1:{args.port}/")
    uvicorn.run(build_app(public), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
