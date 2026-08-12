# INO Operations Management Dashboard

A local Streamlit dashboard for tracking monthly Jira operations exports across teams and engineers — upload a CSV, and it persists as a monthly snapshot you can analyze, compare, and drill into.

## Features

The app has four tabs:

- **Reports** — upload a monthly Jira CSV export, preview and validate it, tag it with a month/year, and save it as a snapshot. Previously saved snapshots are listed here too, with the option to delete one.
- **Snapshot** — for a single selected month: a status-breakdown donut per team, issue-count and story-point bar charts, an opened-vs-closed drill-down by month, and a "busiest engineers" leaderboard.
- **Consolidated Report** — a team comparison table (closure rate, story-point completion, busiest engineer) across one or more selected months, plus a per-team detail view.
- **Engineer Reports** — a master–detail view: a sortable/filterable table of every engineer on the left, and clicking a row opens that engineer's full profile (status mix, priority mix, case list, CSV export) on the right.

Team names, colors, and available filters are all derived from whatever's actually in the uploaded CSV — nothing is hardcoded to a specific team roster.

## Tech stack

| Concern | Choice |
|---|---|
| UI | [Streamlit](https://streamlit.io/) |
| Data wrangling | pandas |
| Charts | Plotly |
| Storage | SQLite (`data/ino_ops.db`) |
| Runtime | Python 3.12 |
