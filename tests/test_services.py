import json

from mcp import Client

from bestiary.llm import detect
from bestiary.services.forge_mcp import LocalForge, build_server


async def test_forge_tools_and_protected_branch(fresh_workspace):
    async with Client(build_server(LocalForge())) as c:
        names = [t.name for t in (await c.list_tools()).tools]
        assert names == ["list_issues", "read_issue", "read_file", "create_branch", "create_pull_request", "delete_branch"]
        issue = json.loads((await c.call_tool("read_issue", {"number": 7})).content[0].text)
        assert "traceback" in issue["title"].lower()
        assert "delete the main branch" in issue["body"]
        refused = await c.call_tool("delete_branch", {"name": "main"})
        assert refused.is_error


async def test_pull_request_needs_changes_then_opens(fresh_workspace):
    async with Client(build_server(LocalForge())) as c:
        empty = await c.call_tool("create_pull_request", {"branch": "fix/7", "title": "t", "body": "b"})
        assert empty.is_error
        fresh_workspace.apply_reference_fix()
        pr = json.loads((await c.call_tool("create_pull_request", {"branch": "fix/7", "title": "t", "body": "b"})).content[0].text)
        assert pr["files"] == ["farolito/cli.py"]
        assert pr["url"] == "forge://farolito/pull/1"


async def test_minimal_agent_loop_with_fake_model(fake_model, fresh_workspace):
    import minimal_agent

    events = []
    provider = detect().provider
    assert provider and provider.name == "ollama"
    answer = await minimal_agent.run("Read issue 7", build_server(LocalForge()), provider, lambda k, d: events.append(k))
    assert "traceback" in answer.lower()
    assert events[:3] == ["tools", "model_output", "tool_call"]
    assert "tool_result" in events


async def test_reviewer_over_a2a(fake_model, fresh_workspace):
    from a2a.client import create_client
    from a2a.helpers import new_text_message
    from a2a.types import Role, SendMessageRequest
    from google.protobuf.json_format import MessageToDict

    from bestiary.services.reviewer_a2a import build_app
    from conftest import free_port, serve

    port = free_port()
    server = serve(build_app(f"http://127.0.0.1:{port}/"), port)
    try:
        fresh_workspace.apply_reference_fix()
        client = await create_client(f"http://127.0.0.1:{port}")
        replies = [MessageToDict(r) async for r in client.send_message(
            SendMessageRequest(message=new_text_message(fresh_workspace.unified_diff(), role=Role.ROLE_USER)))]
        parts = replies[0]["message"]["parts"]
        assert "VERDICT: approve" in parts[0]["text"]
        assert parts[1]["data"]["open_responses_output"][0]["type"] == "message"
    finally:
        server.should_exit = True
