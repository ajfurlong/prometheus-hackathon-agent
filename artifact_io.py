"""Prometheus artifact I/O and follow-up state for the table capabilities."""

import asyncio
import json
from pathlib import Path

from prometheus_api.agent import EventQueue, MissingInput, RequestContext
from prometheus_api.storage_client import ConnectionConfig

from markdown_parser import parse_markdown
from table_data import TableData, parse_csv


class AgentArtifacts:
    """Keep SDK storage, conversation state and input prompts out of data logic."""

    def __init__(self, agent):
        """Bind the SDK agent without owning its conversation state."""
        self.agent = agent

    async def _ask(
        self,
        params: dict,
        context: RequestContext,
        events: EventQueue,
        fields: list[MissingInput],
        hint: str,
    ) -> dict:
        # Persist only selectors; reload source artifacts after the follow-up.
        """Persist selectors and emit SDK input-required fields for a resumed request."""
        pending = {
            key: value for key, value in params.items() if key not in {"artifacts", "userToken"}
        }
        self.agent.save_context_state(str(context.context_id), {"pending": pending})
        await self.agent.send_input_required(context, events, missing_inputs=fields, hint=hint)
        return {}

    async def _text(
        self, artifact_id: str, params: dict, context: RequestContext
    ) -> tuple[str, str]:
        """Resolve an upload and read at most 8 MB of UTF-8 text off the event loop."""
        if not artifact_id:
            raise ValueError("Upload a file in this conversation and choose its artifact.")
        path = await self.agent.get_artifact_file_path(
            artifact_id, context=context, artifacts=params.get("artifacts")
        )
        if path.stat().st_size > 8_000_000:
            raise ValueError("Please provide a document smaller than 8 MB.")
        reference = self.agent.resolve_artifact_reference(str(context.context_id), artifact_id)
        name = reference.name if reference else path.name
        return await asyncio.to_thread(path.read_text, encoding="utf-8-sig"), name

    async def _markdown(self, params: dict, context: RequestContext) -> list[TableData]:
        """Load a Markdown artifact and require at least one parsed table."""
        text, name = await self._text(
            str(params.get("document_artifact_id") or ""), params, context
        )
        if Path(name).suffix.lower() not in {".md", ".markdown"}:
            raise ValueError(
                "Extract/list tables expects a Markdown (.md) upload; use the plot skill for CSV."
            )
        tables = parse_markdown(text)
        if not tables:
            raise ValueError("No GitHub-flavoured Markdown tables were found in this document.")
        return tables

    async def _load_table(self, params: dict, context: RequestContext) -> TableData:
        """Load an inline table object or a CSV/TSV/JSON artifact as TableData."""
        artifact_id = str(params.get("table_artifact_id") or "")
        reference = self.agent.resolve_artifact_reference(str(context.context_id), artifact_id)
        if reference and isinstance(reference.json_body, dict):
            return TableData.from_dict(reference.json_body)
        text, name = await self._text(artifact_id, params, context)
        reference = self.agent.resolve_artifact_reference(str(context.context_id), artifact_id)
        suffix = Path(name).suffix.lower()
        if suffix == ".json":
            return TableData.from_dict(json.loads(text))
        if suffix not in {".csv", ".tsv"}:
            raise ValueError(
                "Plotting expects a CSV/TSV upload or an extracted table artifact. Extract Markdown first."
            )
        caption = (
            reference.metadata.get("caption") or reference.description
            if reference
            else Path(name).stem
        )
        return parse_csv(
            text, str(caption or Path(name).stem), delimiter="\t" if suffix == ".tsv" else None
        )

    async def _publish(
        self,
        path: Path,
        caption: str,
        mime_type: str,
        context: RequestContext,
        events: EventQueue,
        metadata: dict,
    ):
        """Store a table or PNG in DeepLynx and return its SDK artifact reference."""
        try:
            config = ConnectionConfig.from_env()
        except ValueError:
            raise ValueError(
                "Configure the agent's local DEEPLYNX_* variables before publishing artifacts."
            ) from None
        return await self.agent.send_deeplynx_artifact(
            context=context,
            event_queue=events,
            file_path=path,
            name=path.name,
            description=caption,
            storage_config=config,
            mime_type=mime_type,
            tags=["team1", "table" if mime_type == "text/csv" else "plot"],
            metadata=metadata,
        )
