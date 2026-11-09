"""Shared Streamlit helpers: page setup, cached services, lookups, result banners, chart styling."""
from __future__ import annotations

import os
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from src.exceptions import AppError  # noqa: E402
from src.services.hr_service import ActionResult, HRService  # noqa: E402

PALETTE = ["#1F6F78", "#D9A441", "#5B7C99", "#7A5C8E", "#4F8F6B", "#B5586B", "#8A8D91"]
RISK_COLORS = {"Low": "#4F8F6B", "Medium": "#D9A441", "High": "#B5586B"}
px.defaults.color_discrete_sequence = PALETTE

_CSS = """
<style>
.block-container {padding-top: 2.2rem; max-width: 1250px;}
[data-testid="stMetric"] {background: #EAF0F0; border-left: 4px solid #1F6F78;
    padding: .7rem 1rem; border-radius: 6px;}
[data-testid="stMetricLabel"] p {font-size: .85rem;}
div[data-testid="stForm"] {border: 1px solid #D5E0E0; border-radius: 8px;}
</style>
"""


# --------------------------------------------------------------------------- #
# Page bootstrap
# --------------------------------------------------------------------------- #
def _load_secrets_into_env() -> None:
    """Streamlit Cloud keeps credentials in st.secrets; the DB layer reads os.environ."""
    try:
        for key, value in st.secrets.items():
            if isinstance(value, (str, int, float)) and key not in os.environ:
                os.environ[key] = str(value)
    except Exception:  # noqa: BLE001 - no secrets file locally is fine (.env is used)
        pass


@st.cache_resource(show_spinner=False)
def get_service() -> HRService:
    return HRService()


@st.cache_data(ttl=60, show_spinner=False)
def _database_status() -> Tuple[bool, str]:
    try:
        info = get_service().employees.test_connection()
        return True, f"MySQL {info.get('version', '')}"
    except Exception as exc:  # noqa: BLE001 - show any startup problem to the user
        return False, str(exc)


def setup_page(title: str, icon: str, subtitle: str = "", require_db: bool = True) -> None:
    st.set_page_config(page_title=f"{title} - HR Analytics", page_icon=icon, layout="wide")
    _load_secrets_into_env()
    st.markdown(_CSS, unsafe_allow_html=True)
    st.title(f"{icon} {title}")
    if subtitle:
        st.caption(subtitle)
    ok, detail = _database_status()
    with st.sidebar:
        st.markdown("**Database**")
        (st.success if ok else st.error)(detail if ok else "Not connected")
    if require_db and not ok:
        st.error(f"Cannot reach the database: {detail}")
        st.info("Check `.env` (local) or Secrets (Streamlit Cloud): DB_HOST, DB_PORT, DB_USER, DB_PASSWORD "
                "and DB_SSL_CA / DB_SSL_CA_PEM.")
        st.stop()


def refresh_data() -> None:
    """Call after a successful write so dashboards and lookups re-query."""
    st.cache_data.clear()


# --------------------------------------------------------------------------- #
# Cached lookups
# --------------------------------------------------------------------------- #
@st.cache_data(ttl=300, show_spinner=False)
def departments() -> List[Dict[str, Any]]:
    return get_service().employees.list_departments()


@st.cache_data(ttl=300, show_spinner=False)
def job_roles() -> List[Dict[str, Any]]:
    return get_service().employees.list_job_roles()


@st.cache_data(ttl=600, show_spinner=False)
def category_options(column: str, defaults: Tuple[str, ...]) -> List[str]:
    found = get_service().employees.distinct_values(column)
    return found or list(defaults)


@st.cache_data(ttl=300, show_spinner=False)
def project_status_options() -> List[str]:
    return get_service().projects.status_options()


@st.cache_data(ttl=600, show_spinner=False)
def supports_income() -> bool:
    return get_service().employees.supports_income


def department_picker(label: str = "Department", key: Optional[str] = None, container=st, default_id: Optional[int] = None):
    rows = departments()
    ids = [r["department_id"] for r in rows]
    names = {r["department_id"]: r["department_name"] for r in rows}
    idx = ids.index(default_id) if default_id in ids else 0
    return container.selectbox(label, ids, index=idx, format_func=lambda i: names[i], key=key)


def job_role_picker(label: str = "Job role", key: Optional[str] = None, container=st, default_id: Optional[int] = None):
    rows = job_roles()
    ids = [r["job_role_id"] for r in rows]
    names = {r["job_role_id"]: r["job_title"] for r in rows}
    idx = ids.index(default_id) if default_id in ids else 0
    return container.selectbox(label, ids, index=idx, format_func=lambda i: names[i], key=key)


@st.cache_data(ttl=300, show_spinner=False)
def employee_preview(rows: int) -> pd.DataFrame:
    """First ``rows`` employees (by name) - shown under the search box before anything is typed."""
    return get_service().employees.search(None, limit=rows)


def employee_picker(label: str = "Employee", key: str = "emp", preview_rows: int = 0) -> Optional[int]:
    """Search box + result list. Returns the chosen ``employee_id`` (or None).

    With ``preview_rows`` > 0 a small table of employee details is shown right below the search box:
    the first matches while searching, or the first employees when the box is empty.
    """
    term = st.text_input(f"Search {label.lower()} by name or number", key=f"{key}_term").strip()
    df = get_service().employees.search(term, limit=50) if term else None

    if preview_rows:
        shown = df if df is not None else employee_preview(preview_rows)
        if shown is not None and not shown.empty:
            st.caption(f"First {min(preview_rows, len(shown))} matches" if term
                       else f"First {min(preview_rows, len(shown))} employees - type above to search")
            st.dataframe(shown.drop(columns=["employee_id"]).head(preview_rows), hide_index=True, width="stretch")

    if df is None:
        st.caption("Type at least part of a name, or an exact employee number.")
        return None
    if df.empty:
        st.warning("No employee matches that search.")
        return None
    labels = {int(r.employee_id): f"{r.employee_name} (#{r.employee_number}) - {r.department_name}, {r.job_title}"
              for r in df.itertuples()}
    return st.selectbox(label, list(labels), format_func=lambda i: labels[i], key=f"{key}_pick")


# --------------------------------------------------------------------------- #
# Messages
# --------------------------------------------------------------------------- #
def show_error(exc: Exception) -> None:
    if isinstance(exc, AppError):
        st.error(str(exc))
    else:
        st.error(f"Unexpected error: {exc}")


def show_result(result: ActionResult) -> None:
    """Success banner plus the warehouse-sync outcome."""
    st.success(result.message)
    if result.changes:
        st.dataframe(pd.DataFrame([{"field": k, "before": str(old), "after": str(new)}
                                   for k, (old, new) in result.changes.items()]),
                     hide_index=True, width="stretch")
    if result.sync_error:
        st.warning("Saved in the operational database, but the warehouse update failed. "
                   f"Retry on the *Warehouse sync* page.\n\n{result.sync_error}")
    elif result.sync:
        if result.new_versions:
            st.info(f"Warehouse updated: {result.new_versions} employee history record(s) created (SCD Type 2).")
        else:
            st.caption("Warehouse is up to date.")
        with st.expander("ETL details"):
            st.dataframe(pd.DataFrame([r.as_dict() for r in result.sync]), hide_index=True,
                         width="stretch")


# --------------------------------------------------------------------------- #
# Charts
# --------------------------------------------------------------------------- #
def style_fig(fig, height: int = 380):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=50, b=10), colorway=PALETTE,
                      font=dict(family="sans-serif", size=13, color="#16262B"),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      legend=dict(title_text=""), title_font_size=16)
    fig.update_xaxes(gridcolor="#DCE5E5", zeroline=False)
    fig.update_yaxes(gridcolor="#DCE5E5", zeroline=False)
    return fig


def history_timeline(history: pd.DataFrame):
    """Gantt-style view of an employee's SCD Type 2 versions."""
    d = history.copy()
    today = pd.Timestamp.today().normalize()
    d["from"] = pd.to_datetime(d["start_date"])
    d["to"] = pd.to_datetime(d["end_date"])
    current = d["is_current"].astype(bool)
    d.loc[current, "to"] = d.loc[current, "from"].clip(lower=today) + timedelta(days=1)
    d["version"] = d.apply(lambda r: f"{r['department_name']} | {r['job_role']} | L{r['job_level']}", axis=1)
    d["employee"] = d["employee_name"].fillna("Employee")
    fig = px.timeline(d, x_start="from", x_end="to", y="employee", color="version",
                      hover_data=["monthly_income", "change_reason", "is_current"])
    fig.update_yaxes(title="", visible=False)
    return style_fig(fig, height=230)