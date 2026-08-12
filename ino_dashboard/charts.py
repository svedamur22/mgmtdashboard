"""Plotly figure builders. Colors come from the validated categorical/status
palette in ino_dashboard.processing -- team identity and status meaning stay
fixed across every chart in the app."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .processing import (
    PRIORITY_COLORS,
    PRIORITY_ORDER,
    STATE_COLORS,
    STATUS_GROUP_COLORS,
    STATUS_GROUP_ORDER,
    UNASSIGNED_TEAM_COLOR,
)

SURFACE = "#1a1a19"
INK = "#ffffff"
FONT = dict(family="system-ui, -apple-system, 'Segoe UI', sans-serif", color=INK)
GRID_COLOR = "#2c2c2a"
MUTED = "#c3c2b7"


def _base_layout(fig: go.Figure, title: str, height: int = 380, bottom_margin: int = 40) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, family=FONT["family"], color=INK)),
        font=FONT,
        height=height,
        plot_bgcolor=SURFACE,
        paper_bgcolor=SURFACE,
        margin=dict(l=40, r=20, t=56, b=bottom_margin),
        # Legend sits below the plot, never beside the title, so wrapped multi-row
        # legends (5 status groups) can never collide with the title text above.
        legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5),
    )
    return fig


def status_pie(sub: pd.DataFrame, title: str) -> go.Figure:
    counts = sub.groupby("status_group").size().reindex(STATUS_GROUP_ORDER, fill_value=0)
    counts = counts[counts > 0]
    fig = go.Figure(
        data=[
            go.Pie(
                labels=counts.index,
                values=counts.values,
                hole=0.45,
                sort=False,
                marker=dict(colors=[STATUS_GROUP_COLORS[s] for s in counts.index], line=dict(color=SURFACE, width=2)),
                textinfo="percent",
                hovertemplate="%{label}: %{value} issues (%{percent})<extra></extra>",
            )
        ]
    )
    fig.add_annotation(text=f"{int(counts.sum())}<br>issues", showarrow=False, font=dict(size=14, color=MUTED))
    fig = _base_layout(fig, title, height=400, bottom_margin=110)
    fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5))
    return fig


def status_pie_for_team(df: pd.DataFrame, team: str) -> go.Figure:
    return status_pie(df[df["team"] == team], f"{team} — work by status")


def priority_bar_for_engineer(sub: pd.DataFrame, engineer: str) -> go.Figure:
    counts = sub.groupby("priority").size().reindex(PRIORITY_ORDER, fill_value=0)
    fig = go.Figure(
        data=[
            go.Bar(
                x=counts.index,
                y=counts.values,
                marker=dict(color=[PRIORITY_COLORS[p] for p in counts.index]),
                text=counts.values,
                textposition="outside",
                hovertemplate="%{x}: %{y} issues<extra></extra>",
                width=0.5,
            )
        ]
    )
    fig.update_yaxes(title="Issues", gridcolor=GRID_COLOR, zeroline=False)
    fig.update_xaxes(title=None)
    fig = _base_layout(fig, f"{engineer} — issues by priority", height=340)
    fig.update_layout(showlegend=False)
    return fig


def team_totals_bar(df: pd.DataFrame, metric: str, teams: list[str], team_colors: dict[str, str]) -> go.Figure:
    """metric: 'issues' or 'story_points'."""
    if metric == "issues":
        totals = df.groupby("team").size().reindex(teams, fill_value=0)
        title, ytitle = "Issue count by team", "Issues"
    else:
        totals = df.groupby("team")["story_points"].sum().reindex(teams, fill_value=0)
        title, ytitle = "Story points by team", "Story points"

    fig = go.Figure(
        data=[
            go.Bar(
                x=teams,
                y=totals.values,
                marker=dict(color=[team_colors[t] for t in teams]),
                text=[f"{v:,.0f}" for v in totals.values],
                textposition="outside",
                hovertemplate="%{x}: %{y:,.0f}<extra></extra>",
                width=0.5,
            )
        ]
    )
    fig.update_yaxes(title=ytitle, gridcolor=GRID_COLOR, zeroline=False)
    fig.update_xaxes(title=None)
    fig = _base_layout(fig, title, height=340)
    fig.update_layout(showlegend=False)
    return fig


def open_closed_trend(df: pd.DataFrame, teams: list[str]) -> go.Figure:
    sub = df[(df["team"].isin(teams)) & (df["month"] != "Unknown")].copy()
    sub["state"] = sub["is_closed"].map({True: "Closed", False: "Open"})

    grouped = sub.groupby(["month", "team", "state"]).size().reset_index(name="count")
    months = sorted(grouped["month"].unique())

    fig = px.bar(
        grouped,
        x="month",
        y="count",
        color="state",
        facet_col="team",
        category_orders={"month": months, "team": teams, "state": ["Open", "Closed"]},
        color_discrete_map=STATE_COLORS,
        barmode="stack",
        labels={"count": "Issues", "month": "Month (by last update)"},
    )
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1], font=dict(size=13)))
    fig.update_yaxes(matches="y", gridcolor=GRID_COLOR, zeroline=False)
    fig.update_xaxes(gridcolor=GRID_COLOR)
    fig.update_traces(hovertemplate="%{x}: %{y} issues<extra></extra>")
    fig = _base_layout(fig, "Open vs closed issues by month, per team", height=420, bottom_margin=70)
    # Facet column headers ("Go Getters", "Tech Pioneers", ...) sit just under the
    # plot area's top edge -- give them their own band, clear of the figure title.
    fig.update_layout(margin=dict(l=40, r=20, t=90, b=70))
    return fig


def busiest_engineers(
    df: pd.DataFrame, team_colors: dict[str, str], top_n: int = 12, open_only: bool = True
) -> go.Figure:
    sub = df[df["is_closed"] == False].copy() if open_only else df.copy()  # noqa: E712
    agg = (
        sub.groupby(["assignee", "team"])
        .agg(issues=("issue_key", "count"), story_points=("story_points", "sum"))
        .reset_index()
        .sort_values("issues", ascending=False)
        .head(top_n)
    )
    agg = agg.iloc[::-1]  # largest at top in a horizontal bar

    fig = go.Figure(
        data=[
            go.Bar(
                x=agg["issues"],
                y=agg["assignee"],
                orientation="h",
                marker=dict(color=[team_colors.get(t, UNASSIGNED_TEAM_COLOR) for t in agg["team"]]),
                text=agg["issues"],
                textposition="outside",
                customdata=agg[["team", "story_points"]],
                hovertemplate="%{y} (%{customdata[0]}): %{x} issues, %{customdata[1]:.1f} pts<extra></extra>",
                showlegend=False,
            )
        ]
    )
    # Manual legend swatches for team color, since a single bar trace can't carry one.
    for t in team_colors:
        if t in agg["team"].values:
            fig.add_trace(go.Bar(x=[None], y=[None], marker=dict(color=team_colors[t]), name=t, showlegend=True))

    fig.update_xaxes(title="Open issues" if open_only else "Total issues", gridcolor=GRID_COLOR, zeroline=False)
    fig.update_yaxes(title=None)
    fig = _base_layout(
        fig,
        "Busiest engineers" + (" (open workload)" if open_only else ""),
        height=max(340, 28 * len(agg)) + 60,
        bottom_margin=70,
    )
    fig.update_layout(barmode="overlay", showlegend=True)
    return fig
