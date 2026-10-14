"""Exercise ordinary orchestrator requests against an already-running platform.

Run in the agent image on the platform network with the agent's .env supplied.
The platform's existing A2A test helpers must be mounted at /tests/system.
Never prints keys, tokens, or resolved LLM configuration.
"""

import asyncio
import json
import os
import uuid
from pathlib import Path

from system.a2a_client import A2AClient


def safe(text):
    text = str(text)
    for name, value in os.environ.items():
        if any(word in name for word in ("KEY", "SECRET", "PASSWORD", "TOKEN")) and len(value) > 6:
            text = text.replace(value, "[redacted]")
    return text[:1200]


async def run_case(client, source, prompt, answers=None):
    conversation = "team1-check-" + uuid.uuid4().hex
    staged = await client.stage_upload(
        source,
        name=source.name,
        mime_type="text/csv" if source.suffix == ".csv" else "text/markdown",
        conversation_id=conversation,
    )

    async def progress(message):
        print(safe(message), flush=True)

    response = await client.send(prompt, conversation, uploaded_files=[staged], on_status=progress)
    asked = []
    for _ in range(4):
        if response.status == "needs_info":
            fields = response.followup_questions or []
            asked.extend(fields)
            print("Requested fields:", safe(json.dumps(fields, default=str)), flush=True)
            if not answers:
                break
            response = await client.send(
                prompt,
                conversation,
                artifacts=response.artifacts,
                followup_answers=answers,
                on_status=progress,
            )
        elif response.status == "plan_ready":
            response = await client.send(
                prompt,
                conversation,
                artifacts=response.artifacts,
                plan_approved=True,
                on_status=progress,
            )
        else:
            break
    artifacts = [
        {
            "name": a.get("name"),
            "mime_type": a.get("mime_type"),
            "artifact_id": a.get("artifact_id"),
            "producer_agent_id": a.get("producer_agent_id"),
        }
        for a in response.artifacts or []
        if "team-1-table-and-plot-agent" == a.get("producer_agent_id")
    ]
    result = {
        "conversation_id": conversation,
        "status": str(response.status),
        "message": safe(response.message),
        "artifacts": artifacts,
        "asked": asked,
    }
    print(json.dumps(result, default=str), flush=True)
    return result


async def main():
    client = A2AClient("http://client-agent:8000", os.environ["AGENT_SECRET"], timeout=180)
    root = Path("/dataset")
    results = []
    results.append(
        await run_case(
            client,
            root / "hollowmere_almanac.md",
            "Extract the table with population data and plot the population of each village over time.",
        )
    )
    results.append(
        await run_case(
            client,
            root / "demo_sightings.csv",
            "Plot this file.",
            {"x_column": "night", "y_column": "mice_sighted"},
        )
    )
    results.append(
        await run_case(
            client,
            root / "symbolic_report.md",
            "Extract the heating measurements table and plot temperature against time.",
        )
    )
    Path("/results/live_verification.json").write_text(
        json.dumps(results, indent=2, default=str) + "\n"
    )
    if not all(
        any(a["mime_type"] == "image/png" for a in result["artifacts"]) for result in results
    ):
        raise SystemExit(
            "One or more workflows did not produce a Team 1 PNG; see sanitized report."
        )


if __name__ == "__main__":
    asyncio.run(main())
