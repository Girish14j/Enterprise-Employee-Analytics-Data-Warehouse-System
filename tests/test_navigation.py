from streamlit_app import _page_specs_for_role


def test_executive_navigation_contains_only_analytics_dashboard():
    assert _page_specs_for_role("Executive") == [
        ("pages/5_Analytics_Dashboard.py", "Analytics dashboard", "📊")
    ]


def test_hr_navigation_includes_app_pages():
    hr_pages = _page_specs_for_role("HR")
    assert len(hr_pages) == 7
    assert hr_pages[0][1] == "Employee analytics"


def test_unauthenticated_navigation_shows_only_login():
    pages = _page_specs_for_role(None)
    assert len(pages) == 1
    assert pages[0] == ("pages/0_Login.py", "Sign in", "🔐")
