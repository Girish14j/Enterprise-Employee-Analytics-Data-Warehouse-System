from datetime import date, timedelta

import pytest

from src.exceptions import ValidationError
from src.models.entities import Employee, Project, Review


def make_employee(**kw):
    base = dict(employee_number=1, first_name="Asha", last_name="Rao", email="Asha.Rao@Example.com",
                department_id=1, job_role_id=1, job_level=2, monthly_income=5000, hire_date=date(2020, 1, 1))
    base.update(kw)
    return Employee(**base)


def test_employee_normalises_and_derives():
    e = make_employee().validate()
    assert e.email == "asha.rao@example.com"
    assert e.full_name == "Asha Rao"
    assert e.to_db_row()["employee_name"] == "Asha Rao"
    assert "employee_id" not in e.to_db_row()


@pytest.mark.parametrize("field,value", [("email", "not-an-email"), ("age", 12), ("job_level", 9),
                                         ("monthly_income", -5), ("overtime", "Maybe")])
def test_employee_rejects_bad_values(field, value):
    with pytest.raises(ValidationError):
        make_employee(**{field: value})


def test_employee_required_and_future_hire():
    with pytest.raises(ValidationError):
        make_employee(first_name=None).validate()
    with pytest.raises(ValidationError):
        make_employee(hire_date=date.today() + timedelta(days=3)).validate()


def test_employee_behaviour():
    e = make_employee(job_level=5).promote()
    assert e.job_level == 5
    e = make_employee(monthly_income=1000).give_raise(10)
    assert e.monthly_income == 1100
    assert make_employee().change_department(4).department_id == 4
    with pytest.raises(ValidationError):
        make_employee(monthly_income=None).give_raise(5)


def test_unknown_field_rejected():
    with pytest.raises(TypeError):
        Employee(nonsense=1)


def test_from_row_splits_name_and_skips_validation():
    e = Employee.from_row({"employee_id": 7, "employee_number": 3, "employee_name": "Ravi Kumar Singh", "age": 5})
    assert (e.first_name, e.last_name) == ("Ravi", "Kumar Singh")
    assert e.age == 5  # trusted DB data is not re-validated


def test_project_rules():
    today = date.today()
    p = Project(project_name="X", department_id=1, start_date=today - timedelta(days=30),
                end_date=today - timedelta(days=1), project_status="Active", budget=100)
    assert p.validate().is_overdue() is True
    assert p.duration_days == 29
    p.close()
    assert p.is_closed and not p.is_overdue()
    with pytest.raises(ValidationError):
        Project(project_name="X", department_id=1, start_date=today, end_date=today - timedelta(days=1),
                project_status="Planned").validate()


def test_review_rules():
    r = Review(employee_id=1, project_id=1, review_date=date(2024, 5, 1), performance_rating=4,
               job_satisfaction=3, review_score=91.5).validate()
    assert r.review_year == 2024 and r.rating_label == "Outstanding" and r.is_high_performer()
    assert r.to_db_row()["review_year"] == 2024
    for bad in (dict(performance_rating=5), dict(review_score=101), dict(job_satisfaction=0)):
        with pytest.raises(ValidationError):
            Review(employee_id=1, project_id=1, review_date=date(2024, 5, 1), **bad)
    with pytest.raises(ValidationError):
        Review(employee_id=1, project_id=1, review_date=date(2024, 5, 1)).validate()
