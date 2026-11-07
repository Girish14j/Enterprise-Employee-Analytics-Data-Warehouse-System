from datetime import date

import streamlit as st

from src.exceptions import AppError
from src.models.entities import Review
from ui.common import employee_picker, get_service, refresh_data, setup_page, show_error, show_result

setup_page("Performance reviews", "📝",
           "Each saved review becomes a row in the warehouse fact table, linked to the employee's record "
           "as it was on the review date.")
svc = get_service()

employee_id = employee_picker("Employee", key="rev")
projects = svc.projects.list_projects(limit=500)

if employee_id and projects.empty:
    st.info("There are no projects yet. Create one first.")
elif employee_id:
    labels = {int(r.project_id): f"#{r.project_id} - {r.project_name}" for r in projects.itertuples()}
    scale_lo, scale_hi = Review.SCALE
    scale = list(range(scale_lo, scale_hi + 1))

    with st.form("review_form"):
        c1, c2 = st.columns(2)
        project_id = c1.selectbox("Project", list(labels), format_func=lambda i: labels[i])
        review_date = c2.date_input("Review date", value=date.today(), max_value=date.today())
        rating = c1.select_slider("Performance rating", scale, value=scale[-2] if len(scale) > 1 else scale[0],
                                  format_func=lambda r: f"{r} - {Review.RATING_LABELS.get(r, '')}")
        satisfaction = c2.select_slider("Job satisfaction", scale, value=scale[-2] if len(scale) > 1 else scale[0])
        score = st.slider("Review score (0-100)", 0, 100, 75)
        submitted = st.form_submit_button("Submit review", type="primary")

    if submitted:
        try:
            review = Review(employee_id=employee_id, project_id=project_id, review_date=review_date,
                            performance_rating=rating, job_satisfaction=satisfaction, review_score=score)
            with st.spinner("Saving and updating the warehouse..."):
                result = svc.submit_review(review)
            refresh_data()
            show_result(result)
        except AppError as exc:
            show_error(exc)

    st.divider()
    st.subheader("This employee's reviews")
    history = svc.reviews.list_recent(limit=25, employee_id=employee_id)
    if history.empty:
        st.caption("No reviews recorded yet.")
    else:
        st.dataframe(history.drop(columns=["employee_number", "employee_name"]), hide_index=True,
                     width="stretch")
