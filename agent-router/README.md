# Agent Router (encounter 9, side quest)

Agent Router (formerly Envoy AI Gateway) gives apps one OpenAI-compatible endpoint
for many model providers, with routing, failover and token quotas.

On stage it is shown from a recorded run. To record it (Linux or macOS only,
because `aigw run` supports those two):

```bash
# 1. Ollama running with the stage model
ollama pull qwen3.5:9b

# 2. Start Agent Router in standalone mode, pointing at Ollama
OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=unused aigw run
#    (it listens on http://localhost:1975)

# 3. In another terminal, record the replay
uv run python agent-router/record.py
```

The recording is saved to `replays/e9_agent_router.json` and the game shows it
with a REPLAY badge and the recording date.

Check the current flags with `aigw run --help` before recording; the CLI moved
from envoyproxy/ai-gateway to theagentrouter/agent-router in September 2026.
Docs: https://theagentrouter.ai/docs/cli/aigwrun/
