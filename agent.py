"""Team 1 A2A adapter; parsing, selection and plotting live in capabilities."""

import logging
from typing import Any

from prometheus_api.agent import EventQueue, PrometheusAgent, RequestContext

from capabilities import TableCapabilities


class TablePlotAgent(PrometheusAgent):
    """Dispatch advertised skills and resume SDK conversation follow-ups."""

    async def _execute(
        self, params: dict[str, Any], context: RequestContext, event_queue: EventQueue
    ) -> dict:
        """Dispatch one skill after merging validated follow-up answers into saved selectors."""
        skill = params.get("skill_id")
        capabilities = TableCapabilities(self)
        handlers = {
            "team1_extract_table": capabilities._extract,
            "team1_plot_table": capabilities._plot,
            "team1_list_tables": capabilities._list,
        }
        handler = handlers.get(skill)
        if handler is None:
            return {"status": "error", "message": "Unknown table/plot skill."}
        pending = self.load_context_state(str(context.context_id)).get("pending", {})
        merged = dict(pending) if pending.get("skill_id") == skill else {}
        merged.update(params)
        merged.update(self.get_provided_inputs(context))
        try:
            return await handler(merged, context, event_queue)
        except (ValueError, FileNotFoundError, UnicodeError) as exc:
            return {"status": "error", "message": str(exc)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    TablePlotAgent(agent_name="Team 1 Table and Plot Agent").run()
