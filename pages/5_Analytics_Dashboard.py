import plotly.express as px
import streamlit as st

from ui.common import PALETTE, RISK_COLORS, get_service, setup_page, show_error, style_fig

setup_page("Analytics dashboard", "📊",
           "Reads only from the data warehouse (star schema). Figures update after each ETL sync.")
analytics = get_service().analytics

FLAG_COLORS = {"Overdue": RISK_COLORS["High"], "Low performance": RISK_COLORS["Medium"],
               "On track": PALETTE[0], "Completed": "#B8C2C4"}


# Cached query wrappers (managers are not hashable, so the cache sits on module functions)
@st.cache_data(ttl=300, show_spinner="Loading...")
def q_kpis():
    return analytics.kpis()


@st.cache_data(ttl=300, show_spinner="Loading...")
def q_departments():
    return analytics.departments()


@st.cache_data(ttl=300, show_spinner="Loading...")
def q_years():
    return analytics.years()


@st.cache_data(ttl=300, show_spinner="Loading...")
def q_yoy(dept):
    return analytics.yoy_performance(dept)


@st.cache_data(ttl=300, show_spinner="Loading...")
def q_yoy_dept():
    return analytics.yoy_by_department()


@st.cache_data(ttl=300, show_spinner="Loading...")
def q_top(year, top_n, dept, min_reviews):
    return analytics.top_performers(year, top_n, dept, min_reviews)


@st.cache_data(ttl=300, show_spinner="Loading...")
def q_attrition(group):
    return analytics.attrition_by(group)


@st.cache_data(ttl=300, show_spinner="Scoring all employees...")
def q_risk_summary():
    return analytics.attrition_risk_summary()


@st.cache_data(ttl=300, show_spinner="Loading...")
def q_risk(limit, dept):
    return analytics.attrition_risk(limit, dept)


@st.cache_data(ttl=300, show_spinner="Loading...")
def q_projects():
    return analytics.project_bottlenecks()


@st.cache_data(ttl=300, show_spinner=False)
def q_attrition_available():
    return analytics.attrition_available


try:
    depts = q_departments()
    dept_names = dict(zip(depts["department_sk"], depts["department_name"]))
    years = q_years()
    kpi = q_kpis()
except Exception as exc:  # noqa: BLE001
    show_error(exc)
    st.stop()

# ---- sidebar filters ------------------------------------------------------------------------ #
with st.sidebar:
    st.markdown("**Filters**")
    dept_sk = st.selectbox("Department", [None, *dept_names], format_func=lambda k: "All departments" if k is None
                           else dept_names[k])
    year_sel = st.selectbox("Year (top performers)", [None, *years],
                            format_func=lambda y: "All years" if y is None else str(y))
    top_n = st.slider("Top N per department", 3, 10, 5)
    min_reviews = st.slider("Minimum reviews per employee", 1, 5, 2,
                            help="Ranks employees only if they have at least this many reviews, so one lucky "
                                 "review cannot beat a consistent record. With a single year selected, most "
                                 "employees have one review - set this to 1.")

# ---- KPI strip -------------------------------------------------------------------------------- #
c1, c2, c3, c4 = st.columns(4)
c1.metric("Current employees", f"{int(kpi.get('current_employees') or 0):,}")
c2.metric("Reviews", f"{int(kpi.get('total_reviews') or 0):,}")
c3.metric("Average score", f"{float(kpi.get('avg_score') or 0):.1f}")
c4.metric("Average rating", f"{float(kpi.get('avg_rating') or 0):.2f}")

tab_yoy, tab_top, tab_attr, tab_proj = st.tabs(
    ["Year-over-year trends", "Top performers", "Attrition risk", "Project bottlenecks"])

# =============================================================================================== #
with tab_yoy:
    yoy = q_yoy(dept_sk)
    if yoy.empty:
        st.info("No review data for this selection.")
    else:
        change = yoy.dropna(subset=["score_change"])
        if not change.empty:
            biggest = float(change["score_change"].abs().max())
            st.caption(f"Year-to-year movement is small: the largest change is {biggest:.2f} points on a 0-100 "
                       "scale. The charts zoom in on the axis, so differences look larger than they are.")
        left, right = st.columns(2)
        fig = px.line(yoy, x="review_year", y="avg_score", markers=True, text="avg_score",
                      title="Average review score by year" + (f" - {dept_names[dept_sk]}" if dept_sk else ""),
                      labels={"review_year": "Year", "avg_score": "Average score"})
        fig.update_traces(textposition="top center")
        fig.update_xaxes(dtick=1)
        left.plotly_chart(style_fig(fig), width="stretch")

        if change.empty:
            right.info("Need at least two years of data for a year-over-year change.")
        else:
            change = change.assign(direction=change["score_change"].apply(lambda v: "Up" if v >= 0 else "Down"))
            fig2 = px.bar(change, x="review_year", y="score_change", title="Change vs previous year (points)",
                          labels={"review_year": "Year", "score_change": "Score change"},
                          color="direction", color_discrete_map={"Up": PALETTE[4], "Down": PALETTE[5]},
                          text="score_change")
            fig2.update_layout(showlegend=False)
            fig2.update_xaxes(dtick=1)
            right.plotly_chart(style_fig(fig2), width="stretch")

        by_dept = q_yoy_dept()
        fig3 = px.line(by_dept, x="review_year", y="avg_score", color="department_name", markers=True,
                       title="Average score by department",
                       labels={"review_year": "Year", "avg_score": "Average score", "department_name": ""})
        fig3.update_xaxes(dtick=1)
        st.plotly_chart(style_fig(fig3, 400), width="stretch")
        with st.expander("Data"):
            st.dataframe(yoy, hide_index=True, width="stretch")

# =============================================================================================== #
with tab_top:
    st.caption("Ranked with SQL `DENSE_RANK() OVER (PARTITION BY department ORDER BY average score DESC)`. "
               "Ties share a rank. Employees need the minimum number of reviews set in the sidebar.")
    top = q_top(year_sel, top_n, dept_sk, min_reviews)
    if top.empty:
        st.info("No employee has that many reviews for this selection. Lower the minimum in the sidebar.")
    else:
        top = top.assign(label=top["dept_rank"].astype(int).astype(str) + ". " + top["employee_name"])
        fig = px.bar(top, x="avg_score", y="label", color="department_name", orientation="h",
                     facet_col="department_name", facet_col_wrap=2, facet_col_spacing=0.22,
                     facet_row_spacing=0.15, hover_data=["avg_rating", "review_count"],
                     title="Top performers by department" + (f" - {year_sel}" if year_sel else ""),
                     labels={"avg_score": "Average score", "label": ""})
        fig.update_yaxes(matches=None, showticklabels=True, autorange="reversed")
        fig.update_xaxes(matches=None, range=[max(0, top["avg_score"].min() - 10), 100])
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        fig.update_layout(showlegend=False)
        rows = -(-top["department_name"].nunique() // 2)
        st.plotly_chart(style_fig(fig, 260 * rows + 60), width="stretch")
        st.dataframe(top.drop(columns=["label"]), hide_index=True, width="stretch")

# =============================================================================================== #
with tab_attr:
    if q_attrition_available():
        group = st.radio("Group by", ["department", "job_role"], horizontal=True,
                         format_func=lambda g: "Department" if g == "department" else "Job role")
        att = q_attrition(group)
        left, right = st.columns(2)
        fig = px.bar(att.sort_values("attrition_rate"), x="attrition_rate", y="grp", orientation="h",
                     title="Attrition rate (%)", labels={"attrition_rate": "Attrition rate (%)", "grp": ""},
                     hover_data=["headcount", "leavers"])
        left.plotly_chart(style_fig(fig, max(300, 34 * len(att) + 80)), width="stretch")
        right.dataframe(att, hide_index=True, width="stretch")
    else:
        st.info("The warehouse employee table has no attrition column, so attrition rate is skipped.")

    st.subheader("Employees to check in with")
    st.caption("Current employees who have not left. Risk score (0-100) from the latest review: satisfaction of 2 "
               "or lower (40), score fell 10+ points (20), score below department average (20), income below 80% "
               "of department average (20). Low is 0-20, Medium 25-40, High above 40.")
    summary = q_risk_summary()
    if dept_sk:
        summary = summary[summary["department_name"] == dept_names[dept_sk]]
    if summary.empty:
        st.info("No reviewed current employees found.")
    else:
        bands = (summary.groupby("risk_band")["employees"].sum()
                 .reindex(["High", "Medium", "Low"]).fillna(0).astype(int))
        total = int(bands.sum())
        m1, m2, m3 = st.columns(3)
        for col, band in zip((m1, m2, m3), ("High", "Medium", "Low")):
            col.metric(f"{band} risk ({100 * bands[band] / total:.0f}%)", f"{bands[band]:,}")
        st.caption(f"Based on {total:,} current employees with at least one review.")

        left, right = st.columns(2)
        by_dept = summary.groupby(["department_name", "risk_band"], as_index=False)["employees"].sum()
        fig = px.bar(by_dept, x="department_name", y="employees", color="risk_band", barmode="stack",
                     color_discrete_map=RISK_COLORS, category_orders={"risk_band": ["Low", "Medium", "High"]},
                     title="Employees by department and risk band",
                     labels={"department_name": "", "employees": "Employees", "risk_band": ""})
        left.plotly_chart(style_fig(fig, 360), width="stretch")
        dist = summary.groupby(["risk_score", "risk_band"], as_index=False)["employees"].sum()
        fig2 = px.bar(dist, x="risk_score", y="employees", color="risk_band", color_discrete_map=RISK_COLORS,
                      title="Employees by risk score",
                      labels={"risk_score": "Risk score", "employees": "Employees", "risk_band": ""})
        fig2.update_xaxes(dtick=20)
        right.plotly_chart(style_fig(fig2, 360), width="stretch")

        n_show = st.slider("Show the highest-risk employees", 10, 200, 50, step=10)
        risk = q_risk(n_show, dept_sk)
        st.dataframe(risk.drop(columns=["department_sk"], errors="ignore"), hide_index=True, width="stretch")

# =============================================================================================== #
with tab_proj:
    st.caption("Overdue = past its end date and not closed. Low performance = open project in the bottom quarter by "
               "average review score (`NTILE(4)`). Completed projects are shown separately.")
    proj = q_projects()
    if proj.empty:
        st.info("No projects in the warehouse yet.")
    else:
        if dept_sk:
            proj = proj[proj["department_name"] == dept_names[dept_sk]]
        counts = proj["bottleneck_flag"].value_counts()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Overdue", int(counts.get("Overdue", 0)))
        m2.metric("Low performance", int(counts.get("Low performance", 0)))
        m3.metric("On track", int(counts.get("On track", 0)))
        m4.metric("Completed", int(counts.get("Completed", 0)))
        if int(counts.get("Overdue", 0)) == 0:
            st.caption("No project is overdue: open projects have no end date set, so they cannot be late.")

        open_projects = proj[(proj["bottleneck_flag"] != "Completed")].dropna(subset=["avg_score", "avg_satisfaction"])
        if open_projects.empty:
            st.info("There are no open projects with reviews to plot.")
        else:
            fig = px.scatter(open_projects, x="avg_satisfaction", y="avg_score", color="bottleneck_flag",
                             size=open_projects["review_count"].clip(lower=1),
                             hover_data=["project_name", "department_name", "project_status"],
                             color_discrete_map=FLAG_COLORS, title="Open projects: health",
                             labels={"avg_satisfaction": "Average job satisfaction",
                                     "avg_score": "Average review score"})
            st.plotly_chart(style_fig(fig, 420), width="stretch")

        by_dept = (proj.groupby("department_name")["bottleneck_flag"].value_counts().rename("projects")
                   .reset_index())
        fig2 = px.bar(by_dept, x="department_name", y="projects", color="bottleneck_flag", barmode="stack",
                      title="Projects by department and status", color_discrete_map=FLAG_COLORS,
                      labels={"department_name": "", "projects": "Projects", "bottleneck_flag": ""})
        st.plotly_chart(style_fig(fig2), width="stretch")

        flagged = proj[proj["bottleneck_flag"].isin(["Overdue", "Low performance"])]
        st.markdown("**Projects needing attention**")
        if flagged.empty:
            st.success("No open project needs attention.")
        else:
            st.dataframe(flagged.drop(columns=["project_sk"]), hide_index=True, width="stretch")