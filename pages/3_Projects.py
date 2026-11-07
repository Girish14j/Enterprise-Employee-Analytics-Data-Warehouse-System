from datetime import date, timedelta

import streamlit as st

from src.exceptions import AppError
from src.models.entities import Project
from ui.common import (department_picker, employee_picker, get_service, project_status_options, refresh_data,
                       setup_page, show_error, show_result)

setup_page("Projects", "📁", "Create projects, then staff them. New projects are copied to the warehouse automatically.")
svc = get_service()

tab_create, tab_assign, tab_list = st.tabs(["Create project", "Assign employees", "All projects"])

# --------------------------------------------------------------------------- #
with tab_create:
    with st.form("project_form"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Project name")
        department_id = department_picker("Owning department", container=c2, key="proj_dept")
        start = c1.date_input("Start date", value=date.today())
        has_end = c2.checkbox("Has a planned end date", value=True)
        end = c2.date_input("End date", value=date.today() + timedelta(days=365))
        status = c1.selectbox("Status", project_status_options())
        budget = c2.number_input("Budget", min_value=0.0, step=1000.0, value=0.0)
        submitted = st.form_submit_button("Create project", type="primary")

    if submitted:
        try:
            project = Project(project_name=name, department_id=department_id, start_date=start,
                              end_date=end if has_end else None, project_status=status,
                              budget=budget if budget > 0 else None)
            with st.spinner("Saving..."):
                result = svc.create_project(project)
            refresh_data()
            show_result(result)
        except AppError as exc:
            show_error(exc)

# --------------------------------------------------------------------------- #
with tab_assign:
    projects = svc.projects.list_projects(limit=500)
    if projects.empty:
        st.info("Create a project first.")
    else:
        labels = {int(r.project_id): f"#{r.project_id} - {r.project_name} ({r.department_name})"
                  for r in projects.itertuples()}
        project_id = st.selectbox("Project", list(labels), format_func=lambda i: labels[i], key="assign_project")
        employee_id = employee_picker("Employee to assign", key="assign_emp")
        c1, c2 = st.columns(2)
        allocation = c1.slider("Allocation (%)", 5, 100, 100, step=5)
        primary = c2.checkbox("Primary assignment")
        if st.button("Assign employee", type="primary", disabled=employee_id is None):
            try:
                show_result(svc.assign_employee(int(employee_id), int(project_id), float(allocation), primary))
                refresh_data()
            except AppError as exc:
                show_error(exc)

        st.markdown("**Current team**")
        team = svc.projects.list_assignments(int(project_id))
        if team.empty:
            st.caption("Nobody is assigned yet.")
        else:
            st.dataframe(team, hide_index=True, width="stretch")

# --------------------------------------------------------------------------- #
with tab_list:
    f1, f2 = st.columns(2)
    dept_filter = f1.checkbox("Filter by department")
    dept_id = department_picker("Department", container=f1, key="list_dept") if dept_filter else None
    status_filter = f2.selectbox("Status", ["All"] + project_status_options())
    df = svc.projects.list_projects(department_id=dept_id, status=None if status_filter == "All" else status_filter)
    st.caption(f"{len(df):,} project(s)")
    st.dataframe(df, hide_index=True, width="stretch")
