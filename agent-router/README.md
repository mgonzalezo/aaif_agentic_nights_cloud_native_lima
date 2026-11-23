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
the small model. The proof is on screen twice: the `model` field of the response, and the router's
own metrics (`gen_ai_backend` per request, on port 1064):

```bash
kubectl -n bestiary exec deploy/console -c console -- curl -s http://agent-router:1064/metrics | grep request_duration_seconds_count
```

The step only reports a failover if the model that answered really differs; otherwise it falls
back (and no replay is recorded). Standalone `aigw run` does not forward Envoy's access log to
the pod's output, so `kubectl logs` shows only startup lines.

## On a laptop (REPLAY or DIDACTIC)

`aigw run` supports Linux and macOS. To record a replay against a local Ollama:

```bash
OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=unused aigw run   # listens on :1975
uv run python agent-router/record.py
```

The recording is saved to `replays/e9_agent_router.json` and shown with a REPLAY badge and the
recording date. Without it, the encounter is DIDACTIC, and says so.
Check `aigw run --help` first: the CLI moved from envoyproxy/ai-gateway to theagentrouter/agent-router in September 2026.
