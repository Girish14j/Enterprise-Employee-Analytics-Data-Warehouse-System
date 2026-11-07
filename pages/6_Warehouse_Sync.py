import pandas as pd
import plotly.express as px
import streamlit as st

from src.exceptions import AppError
from ui.common import get_service, history_timeline, refresh_data, setup_page, show_error, style_fig

setup_page("Warehouse sync", "🔁",
           "Forms already sync after every save. Use this page to check data quality, retry a failed sync, "
           "or inspect an employee's history.")
svc = get_service()

tab_sync, tab_quality, tab_history = st.tabs(["Sync", "Data quality", "Employee history"])

# --------------------------------------------------------------------------- #
with tab_sync:
    st.markdown("**Pending work** (what a full sync would do right now)")
    try:
        pending = svc.etl.pending_changes()
    except AppError as exc:
        show_error(exc)
        st.stop()
    c1, c2, c3 = st.columns(3)
    c1.metric("Employees with a new version", f"{pending['changed_employees']:,}")
    c2.metric("New employees", f"{pending['new_employees']:,}")
    c3.metric("Reviews not yet in the warehouse", f"{pending['reviews_not_in_fact']:,}")

    total = sum(pending.values())
    if pending["changed_employees"] > 200:
        st.warning("Many employees would get a new history record. If you did not change that many people, "
                   "the warehouse and operational data may disagree - review before running.")
    confirm = st.checkbox("I have reviewed the pending work", disabled=total == 0)
    if st.button("Run full sync", type="primary", disabled=total == 0 or not confirm):
        try:
            with st.spinner("Syncing hr_oltp to hr_dw..."):
                reports = svc.etl.run_full_sync()
            refresh_data()
            st.success("Sync finished.")
            st.dataframe(pd.DataFrame([r.as_dict() for r in reports]), hide_index=True, width="stretch")
        except AppError as exc:
            show_error(exc)
    if total == 0:
        st.success("The warehouse is up to date.")

# --------------------------------------------------------------------------- #
with tab_quality:
    st.caption("The database does not enforce these SCD2 rules, so the pipeline checks them. Every value should be 0.")
    if st.button("Run checks"):
        try:
            checks = svc.etl.validate_scd2()
            frame = pd.DataFrame({"check": [k.replace("_", " ") for k in checks], "rows": list(checks.values())})
            frame["status"] = frame["rows"].apply(lambda n: "OK" if n == 0 else "Needs attention")
            st.dataframe(frame, hide_index=True, width="stretch")
            if all(v == 0 for v in checks.values()):
                st.success("All checks passed.")
            else:
                st.warning("Some checks found rows. A full sync fixes missing rows; overlapping or duplicate "
                           "current rows need a manual look at dim_employee.")
        except AppError as exc:
            show_error(exc)

    changes = svc.analytics.changes_by_year()
    if not changes.empty:
        fig = px.bar(changes, x="change_year", y="versions", color="reason", barmode="stack",
                     title="Employee history records created per year",
                     labels={"change_year": "Year", "versions": "Records", "reason": ""})
        fig.update_xaxes(dtick=1)
        st.plotly_chart(style_fig(fig, 400), width="stretch")

# --------------------------------------------------------------------------- #
with tab_history:
    number = st.number_input("Employee number", min_value=1, step=1, value=1)
    history = svc.analytics.employee_history(int(number))
    if history.empty:
        st.info("No warehouse record for that employee number.")
    else:
        st.plotly_chart(history_timeline(history), width="stretch")
        st.dataframe(history.drop(columns=["employee_number"]), hide_index=True, width="stretch")
