# Manual system smoke checks

These scripts are development checks, separate from the offline pytest suite. They require a running Prometheus platform, the registered Team 1 agent, configured inference/storage credentials, and the platform's existing `tests/system/a2a_client.py` helper.

- `live_verify.py` uploads three fixtures and sends ordinary chat requests through the orchestrator. It checks routing, extraction, plotting and actual-column follow-up/resume. It does not call the skills directly or provide an execution plan. It writes `live_verification.json`.
- `verify_downloads.py` reads that report, downloads the real DeepLynx PNG/CSV artifacts, checks signatures and axes, and verifies population cells against the source fixture. It makes no LLM calls.

After building the agent image with `make up`, run from the repository root. Use a fresh, empty output directory for each run:

```sh
PLATFORM_PATH=/path/to/prometheus_core/platform
IMAGE=prometheus-hackathon-agent-team1-table-plot-agent:latest
RESULTS=output/live-check
mkdir -p "$RESULTS"

docker run --rm --network prometheus_platform_agent-network \
  --env-file .env --entrypoint python -e PYTHONPATH=/tests:/work \
  -v "$PWD:/work:ro" \
  -v "$PLATFORM_PATH/tests/system:/tests/system:ro" \
  -v "$PWD/tests/fixtures:/dataset:ro" \
  -v "$PWD/$RESULTS:/results" \
  -w /work "$IMAGE" scripts/live_verify.py
```

Run the same command with `scripts/verify_downloads.py` after the live check succeeds. Replace `IMAGE` with your actual Compose-built image name if the checkout/project name differs. Both scripts print sanitized progress only; do not print the local `.env` or resolved LLM configuration when debugging.
