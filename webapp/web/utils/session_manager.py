"""
Session Manager - Centralized session state management
Handles filter states for summary dashboard
"""

from flask import session
from typing import List, Optional
from datetime import datetime


class SummarySessionManager:
    """Manages session state for summary dashboard filters"""

    # Session keys
    KEY_SELECTED_SCOPES = "summary_selected_scopes"
    KEY_SELECTED_SUB_SCOPES = "summary_selected_sub_scopes"
    KEY_SELECTED_YEAR = "summary_selected_year"
    KEY_TIME_PERIOD = "summary_time_period"

    @classmethod
    def get_selected_scopes(cls) -> List[str]:
        """Get selected scope IDs from session"""
        return session.get(cls.KEY_SELECTED_SCOPES, [])

    @classmethod
    def set_selected_scopes(cls, scope_ids: List[str]) -> None:
        """Set selected scope IDs in session"""
        session[cls.KEY_SELECTED_SCOPES] = scope_ids

    @classmethod
    def get_selected_sub_scopes(cls) -> List[str]:
        """Get selected sub scope IDs from session"""
        return session.get(cls.KEY_SELECTED_SUB_SCOPES, [])

    @classmethod
    def set_selected_sub_scopes(cls, sub_scope_ids: List[str]) -> None:
        """Set selected sub scope IDs in session"""
        session[cls.KEY_SELECTED_SUB_SCOPES] = sub_scope_ids

    @classmethod
    def get_selected_year(cls) -> int:
        """Get selected year from session or default to current year"""
        return session.get(cls.KEY_SELECTED_YEAR, datetime.now().year)

    @classmethod
    def set_selected_year(cls, year: int) -> None:
        """Set selected year in session"""
        session[cls.KEY_SELECTED_YEAR] = year

    @classmethod
    def get_time_period(cls) -> str:
        """Get time period from session or default to 'week'"""
        return session.get(cls.KEY_TIME_PERIOD, "week")

    @classmethod
    def set_time_period(cls, period: str) -> None:
        """Set time period in session"""
        session[cls.KEY_TIME_PERIOD] = period

    @classmethod
    def update_from_form(cls, form_data: dict) -> None:
        """Update session from form data"""
        if "selected_scopes" in form_data:
            cls.set_selected_scopes(form_data.getlist("selected_scopes"))

        if "selected_sub_scopes" in form_data:
            cls.set_selected_sub_scopes(form_data.getlist("selected_sub_scopes"))

        if "selected_year" in form_data:
            try:
                year = int(form_data.get("selected_year"))
                cls.set_selected_year(year)
            except (TypeError, ValueError):
                pass

        if "time_period" in form_data:
            cls.set_time_period(form_data.get("time_period"))

    @classmethod
    def get_all_filters(cls) -> dict:
        """Get all filter states as a dictionary"""
        return {
            "selected_scopes": cls.get_selected_scopes(),
            "selected_sub_scopes": cls.get_selected_sub_scopes(),
            "selected_year": cls.get_selected_year(),
            "time_period": cls.get_time_period(),
        }

    @classmethod
    def clear_all(cls) -> None:
        """Clear all summary filters from session"""
        for key in [
            cls.KEY_SELECTED_SCOPES,
            cls.KEY_SELECTED_SUB_SCOPES,
            cls.KEY_SELECTED_YEAR,
            cls.KEY_TIME_PERIOD,
        ]:
            session.pop(key, None)
