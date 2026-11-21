"""A fake model server that speaks just enough Ollama + Open Responses for tests.

First call with tools: asks for read_issue(7). After a tool result: answers in text.
"""

from __future__ import annotations

import argparse

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

MODEL = "qwen3.5:9b"


async def tags(_: Request) -> JSONResponse:
    return JSONResponse({"models": [{"name": MODEL}]})


async def responses(request: Request) -> JSONResponse:
    body = await request.json()
    items = body.get("input")
    has_result = isinstance(items, list) and any(i.get("type") == "function_call_output" for i in items)
    if body.get("tools") and not has_result:
        output = [{"type": "function_call", "id": "fc_1", "call_id": "call_1", "name": "read_issue",
                   "arguments": '{"number": 7}', "status": "completed"}]
    else:
        text = "Missing config files crash with a traceback instead of a friendly error."
        if isinstance(items, str) and items.startswith("Review this diff"):
            text = "- Catches FileNotFoundError\n- Message starts with 'farolito: '\n- Exits with 2\nVERDICT: approve"
        output = [{"type": "message", "id": "msg_1", "role": "assistant", "status": "completed",
                   "content": [{"type": "output_text", "text": text, "annotations": []}]}]
    return JSONResponse({"id": "resp_1", "object": "response", "model": body.get("model"), "output": output})


app = Starlette(routes=[Route("/api/tags", tags), Route("/v1/responses", responses, methods=["POST"])])

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=11555)
    uvicorn.run(app, host="127.0.0.1", port=ap.parse_args().port, log_level="warning")
