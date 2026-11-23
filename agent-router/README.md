# Agent Router (encounter 9, side quest)

Agent Router (formerly Envoy AI Gateway) gives apps one OpenAI-compatible endpoint for many
model backends, with routing, failover and token quotas. Docs: https://theagentrouter.ai/docs/

## In the cloud profile (LIVE)

`k8s/overlays/ec2/agent-router.yaml` runs it in standalone mode (`aigw run`, image
`envoyproxy/ai-gateway-cli`, port 1975) with the config in `k8s/overlays/ec2/aigw-config.yaml`:

- priority 0: Service `ollama-main` (the model the client asks for)
- priority 1: Service `ollama-small` (`modelNameOverride` to the small model)
- a retry policy that moves to priority 1 on a refused connection or a 5xx

Both Services select the same Ollama pod (one GPU, one pod). The game simulates the outage by
patching the selector of `ollama-main` (and restores it), then asks again: the answer comes from
the small model. The router's JSON access log shows which backend served each request:

```bash
kubectl -n bestiary logs deploy/agent-router --tail=5
```

## On a laptop (REPLAY or DIDACTIC)

`aigw run` supports Linux and macOS. To record a replay against a local Ollama:

```bash
OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=unused aigw run   # listens on :1975
uv run python agent-router/record.py
```

The recording is saved to `replays/e9_agent_router.json` and shown with a REPLAY badge and the
recording date. Without it, the encounter is DIDACTIC, and says so.
Check `aigw run --help` first: the CLI moved from envoyproxy/ai-gateway to theagentrouter/agent-router in September 2026.
