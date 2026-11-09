from datetime import date

import streamlit as st

from src.exceptions import AppError
from src.models.entities import Employee
from ui.common import (category_options, department_picker, get_service, job_role_picker, refresh_data,
                       setup_page, show_error, show_result, supports_income)

setup_page("Onboard employee", "🧑‍💼",
           "Saves the employee to the operational database, then creates their first warehouse record.")
svc = get_service()

# Banner from the previous save. It is kept in session state so it survives the rerun that
# refreshes the form (new employee number, empty fields).
if "onboard_result" in st.session_state:
    saved_number, saved_result = st.session_state.pop("onboard_result")
    show_result(saved_result)
    st.caption(f"Assigned employee number: {saved_number}")

# Changing this counter gives every widget a new identity, which empties the form after a save.
n = st.session_state.get("onboard_form_n", 0)
next_number = svc.employees.next_employee_number()

with st.form(f"onboard_form_{n}"):
    c1, c2 = st.columns(2)
    first_name = c1.text_input("First name", key=f"onb_first_{n}")
    last_name = c2.text_input("Last name", key=f"onb_last_{n}")
    email = c1.text_input("Work email", key=f"onb_email_{n}")
    c2.text_input("Employee number", value=str(next_number), disabled=True,
                  key=f"onb_number_{next_number}_{n}",
                  help="Assigned automatically: the next free number. It cannot be edited.")
    department_id = department_picker(container=c1, key=f"onb_dept_{n}")
    job_role_id = job_role_picker(container=c2, key=f"onb_role_{n}")
    job_level = c1.number_input("Job level", 1, 5, 1, key=f"onb_level_{n}")
    monthly_income = c2.number_input("Monthly income", min_value=0.0, step=100.0, value=5000.0,
                                     key=f"onb_income_{n}") if supports_income() else None
    hire_date = c1.date_input("Hire date", value=date.today(), max_value=date.today(), key=f"onb_hire_{n}")
    age = c2.number_input("Age", 18, 70, 30, key=f"onb_age_{n}")
    gender = c1.selectbox("Gender", category_options("gender", ("Female", "Male")), key=f"onb_gender_{n}")
    marital_status = c2.selectbox("Marital status", category_options(
        "marital_status", ("Single", "Married", "Divorced")), key=f"onb_marital_{n}")
    business_travel = c1.selectbox("Business travel", category_options(
        "business_travel", ("Non-Travel", "Travel_Rarely", "Travel_Frequently")), key=f"onb_travel_{n}")
    overtime = c2.selectbox("Overtime", category_options("overtime", ("No", "Yes")), key=f"onb_overtime_{n}")
    education_field = c1.selectbox("Education field", category_options(
        "education_field", ("Life Sciences", "Medical", "Marketing", "Technical Degree", "Human Resources",
                            "Other")), key=f"onb_edu_{n}")
    submitted = st.form_submit_button("Save employee", type="primary")

if submitted:
    try:
        # The number is taken again at save time, so it is always the next free one even if
        # someone else onboarded an employee while this form was open.
        employee_number = svc.employees.next_employee_number()
        employee = Employee(
            employee_number=employee_number, first_name=first_name, last_name=last_name, email=email,
            department_id=department_id, job_role_id=job_role_id, job_level=int(job_level),
            monthly_income=monthly_income or None, hire_date=hire_date, age=int(age), gender=gender,
            marital_status=marital_status, business_travel=business_travel, overtime=overtime,
            education_field=education_field, employment_status="Active", attrition="No")
        with st.spinner("Saving and updating the warehouse..."):
            result = svc.onboard_employee(employee)
        refresh_data()
        st.session_state["onboard_result"] = (employee_number, result)
        st.session_state["onboard_form_n"] = n + 1
        st.rerun()
    except AppError as exc:
        show_error(exc)