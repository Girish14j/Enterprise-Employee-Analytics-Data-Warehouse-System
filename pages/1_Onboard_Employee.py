from datetime import date

import streamlit as st

from src.exceptions import AppError
from src.models.entities import Employee
from ui.common import (category_options, department_picker, get_service, job_role_picker, refresh_data,
                       setup_page, show_error, show_result, supports_income)

setup_page("Onboard employee", "🧑‍💼",
           "Saves the employee to the operational database, then creates their first warehouse record.")
svc = get_service()

with st.form("onboard_form"):
    c1, c2 = st.columns(2)
    first_name = c1.text_input("First name")
    last_name = c2.text_input("Last name")
    email = c1.text_input("Work email")
    employee_number = c2.number_input("Employee number", min_value=1, step=1,
                                      value=svc.employees.next_employee_number(),
                                      help="Pre-filled with the next free number.")
    department_id = department_picker(container=c1)
    job_role_id = job_role_picker(container=c2)
    job_level = c1.number_input("Job level", 1, 5, 1)
    monthly_income = c2.number_input("Monthly income", min_value=0.0, step=100.0, value=5000.0) \
        if supports_income() else None
    hire_date = c1.date_input("Hire date", value=date.today(), max_value=date.today())
    age = c2.number_input("Age", 18, 70, 30)
    gender = c1.selectbox("Gender", category_options("gender", ("Female", "Male")))
    marital_status = c2.selectbox("Marital status", category_options("marital_status",
                                                                     ("Single", "Married", "Divorced")))
    business_travel = c1.selectbox("Business travel", category_options(
        "business_travel", ("Non-Travel", "Travel_Rarely", "Travel_Frequently")))
    overtime = c2.selectbox("Overtime", category_options("overtime", ("No", "Yes")))
    education_field = c1.selectbox("Education field", category_options(
        "education_field", ("Life Sciences", "Medical", "Marketing", "Technical Degree", "Human Resources", "Other")))
    submitted = st.form_submit_button("Save employee", type="primary")

if submitted:
    try:
        employee = Employee(
            employee_number=int(employee_number), first_name=first_name, last_name=last_name, email=email,
            department_id=department_id, job_role_id=job_role_id, job_level=int(job_level),
            monthly_income=monthly_income or None, hire_date=hire_date, age=int(age), gender=gender,
            marital_status=marital_status, business_travel=business_travel, overtime=overtime,
            education_field=education_field, employment_status="Active", attrition="No")
        with st.spinner("Saving and updating the warehouse..."):
            result = svc.onboard_employee(employee)
        refresh_data()
        show_result(result)
    except AppError as exc:
        show_error(exc)
