# Team 1 submission status

Team repository: [nshoman/prometheus-hackathon-agent](https://github.com/nshoman/prometheus-hackathon-agent).

Your fork: [ajfurlong/prometheus-hackathon-agent](https://github.com/ajfurlong/prometheus-hackathon-agent).

Agent: **Team 1 Table and Plot Agent**.

Skills: `team1_extract_table`, `team1_plot_table`, `team1_list_tables`.

Workflow: `team1.extract_then_plot`.

The implementation, lockfile, Docker configuration, environment example, fixtures, tests and license notices are included at the repository root. `make demo` generates the population CSV, JSON and PNG locally. Credentials, Python environments, caches and generated outputs are ignored.

This checkout passed all 45 unit tests, Ruff lint/format checks, Docker Compose configuration validation and `git diff --check`. `make demo` produced the population CSV, JSON and PNG from the bundled fixture. The source-file credential scan found no local secrets; `.env`, `.venv/` and generated outputs are ignored.

The renamed Team 1 agent was built, registered and discovered by the platform. The old Hollowmere container and registry entry were replaced, and orchestrator discovery was refreshed. Three ordinary orchestrator workflows succeeded with the new `team1_` skill IDs: population extraction and plotting, a CSV plot after actual-column dropdown answers, and symbolic temperature/time matching. Downloaded PNGs and the population CSV were verified. The local workspace's detailed reports are in `../hackathon/output/team1/`.

The implementation branch is `table-plot-agent`, based on the existing template commit `6490d18d6e8f1af835f88dd95e478896f1696ea6`. The `origin` remote points to your fork and `upstream` points to the teammate's repository. GitHub confirmed the fork relationship. The local `main` branch tracks `origin/main`.

Teammate-reviewed PRs, judge access and the final judged commit SHA remain pending. Pushing this implementation branch alone does not complete the review gate.
