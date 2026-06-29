# Deployment Notes

This project is optimized for local demonstration, but the component boundaries map to a production deployment.

## Recommended Production Changes

- Run the healer API as a replicated service behind a load balancer.
- Use PostgreSQL for audit storage.
- Use shared ChromaDB server mode or another shared vector store for multi-instance deployments.
- Set `REQUIRE_HUMAN_APPROVAL=true` during first rollout.
- Keep `ROLLBACK_DEPLOY` out of `ALLOWED_AUTO_ACTIONS` unless the rollback executor is fully implemented and tested.
- Restrict Docker/Kubernetes credentials to only the namespaces or services the healer is allowed to touch.

## Required Secrets

| Secret | Purpose |
| --- | --- |
| `OPENROUTER_API_KEY` | live diagnosis calls |
| `OPENAI_API_KEY` | OpenAI runbook embeddings |
| `DATABASE_URL` | PostgreSQL audit and approval storage |

## Readiness Checks

- `GET /health` returns the configured audit backend and embedding mode.
- `GET /metrics` exposes healer metrics.
- `GET /audit` returns recent decisions.
- `GET /approval/queue` returns pending human actions.

## Known Limits

- Kubernetes executor remains scaffolded.
- Demo services are intentionally small and synthetic.
- Local hash embeddings are for offline demos and tests, not production semantic retrieval.
