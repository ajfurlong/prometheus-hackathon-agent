"""Verify the real DeepLynx-backed artifacts from live_verify.py; no LLM calls."""

import asyncio
import json
import os
from pathlib import Path

from system.a2a_client import A2AClient

from tables import parse_csv, parse_markdown


async def main():
    client = A2AClient("http://client-agent:8000", os.environ["AGENT_SECRET"])
    results = json.loads(Path("/results/live_verification.json").read_text())
    checks = []
    for label, result, expected_x, expected_y in zip(
        ["population", "csv", "temperature"],
        results,
        ["Year", "night", "t [min]"],
        [["Thistledown", "Mossbury", "Pebblewick"], ["mice_sighted"], ["T [K]"]],
        strict=True,
    ):
        artifacts = await client.list_artifacts(result["conversation_id"])
        png = next(
            a
            for a in artifacts
            if a.get("mime_type") == "image/png"
            and "team-1-table-and-plot-agent" == a.get("producer_agent_id")
        )
        path = Path("/results") / f"live_{label}.png"
        await client.download_artifact(png, path)
        assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        metadata = png.get("metadata") or {}
        assert metadata["x_column"] == expected_x
        assert metadata["y_columns"] == expected_y
        if label == "population":
            table_artifact = next(
                a
                for a in artifacts
                if a.get("mime_type") == "text/csv"
                and "team-1-table-and-plot-agent" == a.get("producer_agent_id")
            )
            table_path = Path("/results/live_population.csv")
            await client.download_artifact(table_artifact, table_path)
            original = parse_markdown(Path("/dataset/hollowmere_almanac.md").read_text())[0]
            actual = parse_csv(table_path.read_text())
            assert actual.columns == original.columns and actual.rows == original.rows
        checks.append(
            {
                "case": label,
                "png_downloaded": True,
                "x_column": expected_x,
                "y_columns": expected_y,
                "missing_values": metadata.get("missing_values"),
            }
        )
    Path("/results/download_verification.json").write_text(json.dumps(checks, indent=2) + "\n")
    print(
        "All three real PNGs downloaded successfully; axes match requests; extracted population CSV exactly matches source."
    )


if __name__ == "__main__":
    asyncio.run(main())
