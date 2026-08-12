import calendar
from datetime import datetime

import pandas as pd
import streamlit as st

from ino_dashboard import charts, processing, storage

st.set_page_config(page_title="INO Operations Dashboard", layout="wide")
storage.init_db()


def period_key_to_label(key: str) -> str:
    try:
        year, month = key.split("-")
        return f"{calendar.month_name[int(month)]} {year}"
    except Exception:
        return key


st.title("INO Operations Management Dashboard")

# Team identity (names + colors) is derived from whatever's actually been uploaded,
# never hardcoded. Computed once here, from every stored period, so a team keeps the
# same color across tabs even when an individual tab is only looking at a subset.
_all_data = storage.load_data()
ALL_TEAMS = processing.get_teams(_all_data) if not _all_data.empty else []
TEAM_COLORS = processing.team_color_map(ALL_TEAMS)

tab_upload, tab_snapshot, tab_report, tab_engineers = st.tabs(
    ["Reports", "Snapshot", "Consolidated Report", "Engineer Reports"]
)

# ---------------------------------------------------------------- Tab 1: Upload
with tab_upload:
    st.subheader("Upload a monthly Jira export")
    st.caption(
        "CSV must include: Issue key, Summary, Assignee, Reporter, Status, Priority, "
        "Updated, Due date, Custom field (Assigned Team), Custom field (Story Points)."
    )

    uploaded = st.file_uploader("Choose CSV file", type="csv")

    if uploaded is not None:
        cleaned = None
        try:
            raw = pd.read_csv(uploaded, encoding="utf-8-sig")
            cleaned = processing.clean_dataframe(raw)
        except processing.ValidationError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Couldn't parse this file: {e}")

        if cleaned is not None:
            st.success(f"Parsed {len(cleaned)} issues.")
            st.warning(
                "**Not saved yet.** This is only a preview — the rest of the dashboard "
                "still shows whatever was saved before. Pick the period below and click "
                "**Save** to update it.",
                icon="⚠️",
            )

            suggestion = processing.suggest_period(cleaned)
            now = datetime.now()
            default_year = suggestion[0] if suggestion else now.year
            default_month = suggestion[1] if suggestion else now.month

            # Keying these off the uploaded file's identity forces Streamlit to treat
            # a newly chosen file as a fresh widget, so the suggested month/year
            # actually updates instead of sticking to whatever a previous file left
            # selected (Streamlit ignores `index=` once a widget already has state).
            file_id = f"{uploaded.name}_{uploaded.size}"

            col1, col2 = st.columns(2)
            with col1:
                month_name = st.selectbox(
                    "Period — month",
                    list(calendar.month_name)[1:],
                    index=default_month - 1,
                    key=f"period_month_{file_id}",
                )
            with col2:
                years = list(range(now.year - 3, now.year + 2))
                year = st.selectbox(
                    "Period — year",
                    years,
                    index=years.index(default_year) if default_year in years else 0,
                    key=f"period_year_{file_id}",
                )
            month_num = list(calendar.month_name).index(month_name)
            period_key = f"{year:04d}-{month_num:02d}"
            period_label = f"{month_name} {year}"

            existing = storage.list_periods()
            if not existing.empty and period_key in existing["period"].values:
                prior_count = int(
                    existing.loc[existing.period == period_key, "issue_count"].iloc[0]
                )
                st.warning(
                    f"{period_label} already has {prior_count} issues saved. "
                    "Saving will replace that snapshot."
                )

            st.dataframe(
                cleaned.head(20)[
                    ["issue_key", "summary", "assignee", "team", "status", "priority", "story_points", "updated"]
                ],
                width="stretch",
            )

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total issues", len(cleaned))
            m2.metric("Teams", cleaned["team"].nunique())
            m3.metric("Engineers", cleaned["assignee"].nunique())
            m4.metric("Total story points", f"{cleaned['story_points'].sum():,.1f}")

            if st.button(f"💾 Save as {period_label} — updates the whole dashboard", type="primary"):
                n = storage.save_period(cleaned, period_key)
                # Point every other tab's period selector at what was just saved --
                # otherwise they stay parked on whatever period was picked earlier
                # in the session, which reads as "the app still shows my old data".
                st.session_state["snapshot_period"] = period_key
                st.session_state["report_periods"] = [period_key]
                st.session_state["eng_periods"] = [period_key]
                st.success(f"Saved {n} issues under {period_label}.")
                st.rerun()

    st.divider()
    st.subheader("Stored monthly snapshots")
    periods = storage.list_periods()
    if periods.empty:
        st.info("No data uploaded yet.")
    else:
        display = periods.copy()
        display["Period"] = display["period"].apply(period_key_to_label)
        display = display.rename(
            columns={
                "issue_count": "Issues",
                "uploaded_at": "Uploaded at",
                "min_updated": "Earliest update",
                "max_updated": "Latest update",
            }
        )
        st.dataframe(
            display[["Period", "Issues", "Uploaded at", "Earliest update", "Latest update"]],
            width="stretch",
            hide_index=True,
        )

        to_delete = st.selectbox(
            "Delete a snapshot",
            ["—"] + periods["period"].tolist(),
            format_func=lambda p: "—" if p == "—" else period_key_to_label(p),
        )
        if to_delete != "—" and st.button("Delete selected snapshot"):
            storage.delete_period(to_delete)
            st.rerun()

# -------------------------------------------------------------- Tab 2: Snapshot
with tab_snapshot:
    periods = storage.list_periods()
    if periods.empty:
        st.info("Upload a monthly CSV in the Upload tab first.")
    else:
        period_options = periods["period"].tolist()
        selected_period = st.selectbox(
            "Snapshot period", period_options, format_func=period_key_to_label, key="snapshot_period"
        )
        df = storage.load_data([selected_period])
        teams = processing.get_teams(df)

        st.markdown("### Work allocation by team")
        cols = st.columns(len(teams)) if teams else []
        for col, team in zip(cols, teams):
            with col:
                st.plotly_chart(
                    charts.status_pie_for_team(df, team), width="stretch", key=f"snap_pie_{team}"
                )

        st.markdown("### Team performance")
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(
                charts.team_totals_bar(df, "issues", teams, TEAM_COLORS),
                width="stretch",
                key="snap_bar_issues",
            )
        with c2:
            st.plotly_chart(
                charts.team_totals_bar(df, "story_points", teams, TEAM_COLORS),
                width="stretch",
                key="snap_bar_points",
            )

        st.markdown("### Opened vs. closed drill-down")
        st.caption(
            "This export has no separate 'created' date, so issues are bucketed by their "
            "last-updated month; spans every uploaded month, not just the snapshot above."
        )
        teams_for_trend = st.multiselect("Teams", ALL_TEAMS, default=ALL_TEAMS)
        if teams_for_trend:
            all_periods_df = storage.load_data()
            st.plotly_chart(
                charts.open_closed_trend(all_periods_df, teams_for_trend),
                width="stretch",
                key="snap_trend",
            )

        st.markdown("### Busiest engineers")
        bc1, bc2 = st.columns([1, 3])
        with bc1:
            team_filter = st.multiselect(
                # Keying off the current team set forces a fresh widget (and thus a
                # fresh default) whenever a new upload changes which teams exist --
                # otherwise this stays parked on whatever teams existed the first
                # time this widget ever rendered in the session.
                "Filter by team", teams, default=teams, key=f"busy_team_filter_{'|'.join(teams)}"
            )
            metric_mode = st.radio("Rank by", ["Open workload", "Total assigned"], index=0)
            top_n = st.slider("Show top", 5, 30, 12)
        busy_df = df[df["team"].isin(team_filter)] if team_filter else df
        with bc2:
            if busy_df.empty:
                st.info("No issues match this filter.")
            else:
                st.plotly_chart(
                    charts.busiest_engineers(
                        busy_df, TEAM_COLORS, top_n=top_n, open_only=(metric_mode == "Open workload")
                    ),
                    width="stretch",
                    key="snap_busiest",
                )

# --------------------------------------------------- Tab 3: Consolidated Report
with tab_report:
    periods = storage.list_periods()
    if periods.empty:
        st.info("Upload a monthly CSV in the Upload tab first.")
    else:
        period_options = periods["period"].tolist()
        selected_periods = st.multiselect(
            "Include periods",
            period_options,
            default=[period_options[0]],
            format_func=period_key_to_label,
            key="report_periods",
        )
        if not selected_periods:
            st.warning("Select at least one period.")
        else:
            df = storage.load_data(selected_periods)
            teams = processing.get_teams(df)

            st.markdown("### Team comparison")
            rows = []
            for team in teams:
                sub = df[df["team"] == team]
                total = len(sub)
                closed = int(sub["is_closed"].sum())
                open_ = total - closed
                total_pts = sub["story_points"].sum()
                done_pts = sub.loc[sub["is_closed"], "story_points"].sum()
                top = sub[~sub["is_closed"]].groupby("assignee").size().sort_values(ascending=False)
                busiest = f"{top.index[0]} ({int(top.iloc[0])})" if len(top) else "—"
                rows.append(
                    {
                        "Team": team,
                        "Total issues": total,
                        "Open": open_,
                        "Closed": closed,
                        "Closure rate": f"{closed / total * 100:.0f}%" if total else "—",
                        "Total story points": round(total_pts, 1),
                        "Completed story points": round(done_pts, 1),
                        "Story point completion": f"{done_pts / total_pts * 100:.0f}%" if total_pts else "—",
                        "Engineers": sub["assignee"].nunique(),
                        "Busiest engineer (open)": busiest,
                    }
                )
            report_df = pd.DataFrame(rows)
            st.dataframe(report_df, width="stretch", hide_index=True)
            st.download_button(
                "Download report as CSV",
                report_df.to_csv(index=False).encode(),
                file_name="ino_team_report.csv",
                mime="text/csv",
            )

            st.markdown("### Per-team detail")
            team_tabs = st.tabs(teams)
            for team_tab, team in zip(team_tabs, teams):
                with team_tab:
                    sub = df[df["team"] == team]
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total issues", len(sub))
                    col2.metric("Open", int((~sub["is_closed"]).sum()))
                    col3.metric("Closed", int(sub["is_closed"].sum()))
                    col4.metric(
                        "Story points done",
                        f"{sub.loc[sub['is_closed'], 'story_points'].sum():.1f} / {sub['story_points'].sum():.1f}",
                    )

                    pc1, pc2 = st.columns(2)
                    with pc1:
                        st.plotly_chart(
                            charts.status_pie_for_team(df, team),
                            width="stretch",
                            key=f"report_pie_{team}",
                        )
                    with pc2:
                        priority_counts = sub.groupby("priority").size().sort_values(ascending=False)
                        st.bar_chart(priority_counts)

                    st.markdown("##### Engineers on this team")
                    eng = (
                        sub.groupby("assignee")
                        .agg(
                            open_issues=("is_closed", lambda s: int((~s).sum())),
                            closed_issues=("is_closed", "sum"),
                            story_points=("story_points", "sum"),
                        )
                        .sort_values("open_issues", ascending=False)
                    )
                    st.dataframe(eng, width="stretch", key=f"report_eng_{team}")

# ---------------------------------------------------- Tab 4: Engineer Reports
PRIORITY_RANK = {"Urgent": 0, "High": 1, "Medium": 2, "Low": 3}

with tab_engineers:
    periods = storage.list_periods()
    if periods.empty:
        st.info("Upload a monthly CSV in the Upload tab first.")
    else:
        period_options = periods["period"].tolist()
        selected_periods = st.multiselect(
            "Include periods",
            period_options,
            default=[period_options[0]],
            format_func=period_key_to_label,
            key="eng_periods",
        )
        if not selected_periods:
            st.warning("Select at least one period.")
        else:
            df = storage.load_data(selected_periods)
            teams = processing.get_teams(df)
            df = df.assign(
                closed_points=df["story_points"].where(df["is_closed"], 0.0),
                is_high=df["priority"].isin(processing.HIGH_PRIORITIES),
            )
            df["is_open_high"] = (~df["is_closed"]) & df["is_high"]

            fc1, fc2 = st.columns([1, 2])
            with fc1:
                team_filter = st.multiselect(
                    "Filter by team", teams, default=teams, key=f"eng_team_filter_{'|'.join(teams)}"
                )
            with fc2:
                search = st.text_input("Search engineer name", key="eng_search")

            scoped = df[df["team"].isin(team_filter)] if team_filter else df
            if search:
                scoped = scoped[scoped["assignee"].str.contains(search, case=False, na=False)]

            engineer_agg = (
                scoped.groupby("assignee")
                .agg(
                    Team=("team", lambda s: s.mode().iat[0] if len(s.mode()) else "Unassigned"),
                    **{
                        "Total issues": ("issue_key", "count"),
                        "Open": ("is_closed", lambda s: int((~s).sum())),
                        "Closed": ("is_closed", "sum"),
                        "Story points": ("story_points", "sum"),
                        "Open high-priority": ("is_open_high", "sum"),
                    },
                )
                .reset_index()
                .rename(columns={"assignee": "Engineer"})
            )

            if engineer_agg.empty:
                st.info("No engineers match this filter.")
            else:
                sort_by = st.radio(
                    "Sort by",
                    ["Total issues", "Open", "Story points", "Open high-priority"],
                    horizontal=True,
                    key="eng_sort_by",
                )
                engineer_agg = engineer_agg.sort_values(sort_by, ascending=False).reset_index(drop=True)
                engineer_agg["Story points"] = engineer_agg["Story points"].round(1)

                left, right = st.columns([3, 4])

                with left:
                    st.markdown("##### Engineers")
                    st.caption("Click a row to open that engineer's profile.")
                    event = st.dataframe(
                        engineer_agg,
                        hide_index=True,
                        width="stretch",
                        height=520,
                        on_select="rerun",
                        selection_mode="single-row",
                        key="engineer_select_table",
                    )

                with right:
                    selected_rows = event.selection.rows if event and event.selection else []
                    row_idx = selected_rows[0] if selected_rows else 0
                    row_idx = min(row_idx, len(engineer_agg) - 1)
                    engineer = engineer_agg.iloc[row_idx]["Engineer"]

                    eng_df = scoped[scoped["assignee"] == engineer]
                    teams_str = ", ".join(sorted(eng_df["team"].unique()))

                    st.markdown(f"##### {engineer}")
                    st.caption(f"Team: {teams_str}")

                    k1, k2, k3, k4 = st.columns(4)
                    total = len(eng_df)
                    closed = int(eng_df["is_closed"].sum())
                    open_ = total - closed
                    total_pts = eng_df["story_points"].sum()
                    done_pts = eng_df["closed_points"].sum()
                    k1.metric("Total issues", total)
                    k2.metric("Open", open_)
                    k3.metric("Closed", closed)
                    k4.metric("Closure rate", f"{closed / total * 100:.0f}%" if total else "—")
                    st.metric("Story points completed", f"{done_pts:.1f} / {total_pts:.1f}")

                    pc1, pc2 = st.columns(2)
                    with pc1:
                        st.plotly_chart(
                            charts.status_pie(eng_df, f"{engineer} — work by status"),
                            width="stretch",
                            key="eng_status_pie",
                        )
                    with pc2:
                        st.plotly_chart(
                            charts.priority_bar_for_engineer(eng_df, engineer),
                            width="stretch",
                            key="eng_priority_bar",
                        )

                    st.markdown("###### Case list")
                    high_only = st.checkbox(
                        "Show only High & Urgent priority", value=False, key="eng_high_only"
                    )
                    cases = eng_df.copy()
                    if high_only:
                        cases = cases[cases["is_high"]]
                    cases = cases.assign(_rank=cases["priority"].map(PRIORITY_RANK).fillna(4))
                    cases = cases.sort_values(["_rank", "updated"], ascending=[True, False])

                    st.caption(f"{len(cases)} of {total} issues shown")
                    st.dataframe(
                        cases[["issue_key", "summary", "status", "priority", "story_points", "team", "updated"]],
                        hide_index=True,
                        width="stretch",
                        key="eng_case_table",
                    )
                    st.download_button(
                        f"Download {engineer}'s issues as CSV",
                        cases.to_csv(index=False).encode(),
                        file_name=f"{engineer.replace(' ', '_')}_issues.csv",
                        mime="text/csv",
                        key="eng_download",
                    )
