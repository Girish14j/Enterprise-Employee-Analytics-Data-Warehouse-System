"""Entrypoint: ``streamlit run streamlit_app.py``"""
from __future__ import annotations

from typing import Callable, List, Optional, Tuple, Union

import streamlit as st

from ui.common import get_service, setup_page, show_error

PageSource = Union[str, Callable[[], None]]
PageSpec = Tuple[PageSource, str, str]


def _render_home() -> None:
    setup_page("Employee analytics", "👥",
               "HR operations on the left, warehouse analytics on the right - one connected system.")

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Record changes")
        st.markdown(
            "- **Onboard employee**: add a new hire\n"
            "- **Update employee**: change department, role, level or salary\n"
            "- **Projects**: create projects and staff them\n"
            "- **Reviews**: submit a performance review"
        )
        st.caption("These pages write to the operational database (hr_oltp).")
    with col_b:
        st.subheader("Understand the workforce")
        st.markdown(
            "- **Analytics dashboard**: performance trends, top performers, attrition risk, project bottlenecks\n"
            "- **Warehouse sync**: employee history, data-quality checks, manual sync"
        )
        st.caption("These pages read from the star schema (hr_dw).")

    st.divider()
    st.subheader("Warehouse at a glance")
    try:
        k = get_service().analytics.kpis()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Current employees", f"{int(k.get('current_employees') or 0):,}")
        c2.metric("History records (SCD2)", f"{int(k.get('employee_versions') or 0):,}")
        c3.metric("Performance reviews", f"{int(k.get('total_reviews') or 0):,}")
        c4.metric("Average review score", f"{float(k.get('avg_score') or 0):.1f}")
    except Exception as exc:  # noqa: BLE001
        show_error(exc)

    with st.expander("How data flows"):
        st.markdown(
            "1. A form saves the change to **hr_oltp** (the live, normalized database).\n"
            "2. The ETL pipeline immediately copies it to **hr_dw**. If a department, job role, level or "
            "salary changed, the old employee record is closed and a new one is opened (**SCD Type 2**), "
            "so history is never lost.\n"
            "3. The dashboards read only from **hr_dw**."
        )


def _page_specs_for_role(role: Optional[str]) -> List[PageSpec]:
    dashboard = ("pages/5_Analytics_Dashboard.py", "Analytics dashboard", "📊")
    if role is None:
        return [("pages/0_Login.py", "Sign in", "🔐")]
    if role == "Executive":
        return [dashboard]
    return [
        (_render_home, "Employee analytics", "👥"),
        ("pages/1_Onboard_Employee.py", "Onboard employee", "🧑‍💼"),
        ("pages/2_Update_Employee.py", "Update employee", "🔄"),
        ("pages/3_Projects.py", "Projects", "📁"),
        ("pages/4_Reviews.py", "Performance reviews", "📝"),
        dashboard,
        ("pages/6_Warehouse_Sync.py", "Warehouse sync", "🔁"),
    ]


def main() -> None:
    st.set_page_config(page_title="Employee analytics - HR Analytics", page_icon="👥", layout="wide")
    user = st.session_state.get("auth_user")
    role = user.get("role") if isinstance(user, dict) else None
    specs = _page_specs_for_role(role)
    pages = [
        st.Page(source, title=title, icon=icon, default=index == 0)
        for index, (source, title, icon) in enumerate(specs)
    ]
    st.navigation(pages).run()


if __name__ == "__main__":
    main()
