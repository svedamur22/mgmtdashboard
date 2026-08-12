"""Cleaning and classification rules for INO Jira exports."""

import pandas as pd

RENAME_MAP = {
    "Issue key": "issue_key",
    "Issue id": "issue_id",
    "Summary": "summary",
    "Assignee": "assignee",
    "Assignee Id": "assignee_id",
    "Reporter": "reporter",
    "Reporter Id": "reporter_id",
    "Status": "status",
    "Priority": "priority",
    "Updated": "updated",
    "Due date": "due_date",
    "Custom field (Assigned Team)": "team",
    "Custom field (Story Points)": "story_points",
}

REQUIRED_SOURCE_COLUMNS = list(RENAME_MAP.keys())

# Teams are whatever "Custom field (Assigned Team)" values show up in the uploaded
# CSV -- never hardcoded. Colors are assigned dynamically (see team_color_map) from
# this fixed dark-surface categorical order, so identity stays stable per dataset
# without ever being cycled or reassigned by a filter.
CATEGORICAL_COLORS = [
    "#3987e5",  # blue
    "#d95926",  # orange
    "#199e70",  # aqua
    "#c98500",  # yellow
    "#d55181",  # magenta
    "#008300",  # green
    "#9085e9",  # violet
    "#e66767",  # red
]
UNASSIGNED_TEAM_COLOR = "#898781"

CLOSED_STATUSES = {"Done", "Closed", "Rejected", "Soft Delete", "Withdrawn"}

STATUS_GROUP_MAP = {
    "Done": "Completed",
    "Closed": "Completed",
    "In Progress": "In Progress",
    "In Review": "In Progress",
    "To Do": "Backlog",
    "New": "Backlog",
    "Open": "Backlog",
    "Approved Backlog": "Backlog",
    "Approved": "Backlog",
    "On Hold": "Blocked/Waiting",
    "Waiting for Approval": "Blocked/Waiting",
    "Request Approved": "Blocked/Waiting",
    "Rejected": "Rejected/Withdrawn",
    "Soft Delete": "Rejected/Withdrawn",
    "Withdrawn": "Rejected/Withdrawn",
}

STATUS_GROUP_ORDER = ["Completed", "In Progress", "Backlog", "Blocked/Waiting", "Rejected/Withdrawn"]

STATUS_GROUP_COLORS = {
    "Completed": "#0ca30c",
    "In Progress": "#3987e5",
    "Backlog": "#898781",
    "Blocked/Waiting": "#fab219",
    "Rejected/Withdrawn": "#d03b3b",
}

STATE_COLORS = {"Open": "#3987e5", "Closed": "#0ca30c"}

# Priority is ordinal, so it draws from the single-hue sequential ramp rather than
# the categorical palette -- severity reads as depth, not identity. On the dark
# chart surface, "near zero" recedes toward the surface (darkest) and severity
# brightens, the reverse of the light-surface direction.
PRIORITY_ORDER = ["Low", "Medium", "High", "Urgent"]
PRIORITY_COLORS = {
    "Low": "#184f95",
    "Medium": "#256abf",
    "High": "#3987e5",
    "Urgent": "#86b6ef",
}
HIGH_PRIORITIES = {"High", "Urgent"}


class ValidationError(Exception):
    pass


def validate_columns(raw_df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_SOURCE_COLUMNS if c not in raw_df.columns]
    if missing:
        raise ValidationError(
            "This file is missing columns Jira export expects: " + ", ".join(missing)
        )


def clean_dataframe(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Rename, parse, and classify a raw Jira export into analysis-ready rows."""
    validate_columns(raw_df)

    df = raw_df.rename(columns=RENAME_MAP)[list(RENAME_MAP.values())].copy()

    df["updated"] = pd.to_datetime(df["updated"], format="mixed", errors="coerce")
    df["due_date"] = pd.to_datetime(df["due_date"], format="mixed", errors="coerce")
    df["story_points"] = pd.to_numeric(df["story_points"], errors="coerce").fillna(0.0)

    df["team"] = df["team"].fillna("Unassigned").replace("", "Unassigned")
    df["assignee"] = df["assignee"].fillna("Unassigned").replace("", "Unassigned")
    df["status"] = df["status"].fillna("Unknown")

    df["status_group"] = df["status"].map(STATUS_GROUP_MAP).fillna("Backlog")
    df["is_closed"] = df["status"].isin(CLOSED_STATUSES)
    df["month"] = df["updated"].dt.to_period("M").astype(str)
    df.loc[df["updated"].isna(), "month"] = "Unknown"

    df["issue_key"] = df["issue_key"].astype(str)
    df["issue_id"] = df["issue_id"].astype(str)

    return df


def suggest_period(df: pd.DataFrame) -> tuple[int, int] | None:
    """Return (year, month) of the most common Updated-date month, for pre-filling the period picker."""
    months = df["updated"].dropna()
    if months.empty:
        return None
    mode = months.dt.to_period("M").mode()
    if mode.empty:
        return None
    p = mode.iloc[0]
    return p.year, p.month


def get_teams(df: pd.DataFrame) -> list[str]:
    """Teams present in this dataset, alphabetical, with 'Unassigned' pinned last."""
    values = df["team"].dropna().unique().tolist()
    real = sorted(t for t in values if t != "Unassigned")
    return real + (["Unassigned"] if "Unassigned" in values else [])


def team_color_map(teams: list[str]) -> dict[str, str]:
    """Assign each team a fixed categorical slot, in the order given. Teams past the
    8-color palette (and 'Unassigned') fall back to the shared muted gray."""
    colors = {}
    slot = 0
    for t in teams:
        if t == "Unassigned" or slot >= len(CATEGORICAL_COLORS):
            colors[t] = UNASSIGNED_TEAM_COLOR
        else:
            colors[t] = CATEGORICAL_COLORS[slot]
            slot += 1
    return colors
