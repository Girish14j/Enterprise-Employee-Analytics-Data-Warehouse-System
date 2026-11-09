import streamlit as st

from src.exceptions import AppError
from src.models.entities import EMPLOYMENT_STATUSES
from ui.common import (department_picker, employee_picker, get_service, history_timeline, job_role_picker,
                       refresh_data, setup_page, show_error, show_result, supports_income)

setup_page("Update employee", "🔄",
           "A change to department, job role, level or salary closes the old warehouse record and opens a new "
           "one (SCD Type 2), so history is kept.")
svc = get_service()

employee_id = employee_picker("Employee", key="upd", preview_rows=5)

if employee_id:
    try:
        detail = svc.employees.get_detail(employee_id)
    except AppError as exc:
        show_error(exc)
        st.stop()

    st.subheader(detail["employee_name"])
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Department", detail["department_name"])
    m2.metric("Job role", detail["job_title"])
    m3.metric("Job level", detail.get("job_level") or "-")
    m4.metric("Monthly income", f"{float(detail['monthly_income']):,.0f}" if detail.get("monthly_income") else "-")

    with st.form(f"update_form_{employee_id}"):
        st.markdown("**New values**")
        c1, c2 = st.columns(2)
        department_id = department_picker(container=c1, key=f"dept_{employee_id}",
                                          default_id=detail["department_id"])
        job_role_id = job_role_picker(container=c2, key=f"role_{employee_id}", default_id=detail["job_role_id"])
        job_level = c1.number_input("Job level", 1, 5, int(detail.get("job_level") or 1), key=f"lvl_{employee_id}")
        monthly_income = None
        if supports_income():
            monthly_income = c2.number_input("Monthly income", min_value=0.0, step=100.0,
                                             value=float(detail.get("monthly_income") or 0.0),
                                             key=f"inc_{employee_id}")
        current_status = detail.get("employment_status") or "Active"
        status = c1.selectbox("Employment status", EMPLOYMENT_STATUSES,
                              index=EMPLOYMENT_STATUSES.index(current_status)
                              if current_status in EMPLOYMENT_STATUSES else 0, key=f"st_{employee_id}")
        submitted = st.form_submit_button("Save changes", type="primary")

    if submitted:
        changes = {"department_id": department_id, "job_role_id": job_role_id, "job_level": int(job_level),
                   "employment_status": status}
        if monthly_income:
            changes["monthly_income"] = monthly_income
        try:
            with st.spinner("Saving and updating the warehouse..."):
                result = svc.update_employee(employee_id, changes)
            refresh_data()
            show_result(result)
        except AppError as exc:
            show_error(exc)

    st.divider()
    st.subheader("Version history in the warehouse")
    history = svc.analytics.employee_history(int(detail["employee_number"]))
    if history.empty:
        st.info("No warehouse history yet. Run a sync on the Warehouse sync page.")
    else:
        st.plotly_chart(history_timeline(history), width="stretch")
        st.dataframe(history.drop(columns=["employee_sk", "employee_number"]), hide_index=True,
                     width="stretch")