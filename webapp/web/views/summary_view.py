"""
Summary View - Refactored and Clean Version
All business logic moved to services, clean HTMX endpoints
"""

from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required, current_user
from bson import ObjectId

from ..utils.acl import permissions_required_all
from ..utils.user_context import with_user_context
from ..utils.session_manager import SummarySessionManager
from ..utils.chart_generator import ChartGenerator
from ...services.summary_service import SummaryService
from ...models import Scope

module = Blueprint("summary", __name__, url_prefix="/summary")


# ============================================================================
# MAIN PAGE
# ============================================================================


@module.route("/", methods=["GET"])
@login_required
@permissions_required_all(["เข้าถึงหน้าสรุปผล"])
@with_user_context
def summary():
    """Main summary dashboard page"""
    # Check if selected_year is already in session
    from flask import session

    if SummarySessionManager.KEY_SELECTED_YEAR not in session:
        # First time - initialize with latest year from database
        available_years = SummaryService.get_available_years(
            current_user.campus_id, current_user.department_key
        )
        if available_years:
            latest_year = max(available_years)
            SummarySessionManager.set_selected_year(latest_year)

    selected_year = SummarySessionManager.get_selected_year()

    return render_template(
        "/summary/summary.html", user=current_user, selected_year=selected_year
    )


# ============================================================================
# FILTER DROPDOWNS - HTMX Endpoints
# ============================================================================


@module.route("/scopes", methods=["GET"])
@login_required
@with_user_context
def get_scopes():
    """HTMX endpoint: Load scope dropdown options"""
    unique_scopes = SummaryService.get_unique_scopes(
        current_user.campus_id, current_user.department_key
    )

    return render_template(
        "/summary/partials/scope_dropdown.html", scopes=unique_scopes
    )


@module.route("/sub-scopes", methods=["POST"])
@login_required
@with_user_context
def get_sub_scopes():
    """HTMX endpoint: Load sub scope dropdown filtered by selected scopes"""
    selected_scopes = request.form.getlist("selected_scopes")
    current_selected_sub_scopes = request.form.getlist("selected_sub_scopes")

    sub_scopes = SummaryService.get_filtered_sub_scopes(
        current_user.campus_id,
        current_user.department_key,
        selected_scopes if selected_scopes else None,
    )

    return render_template(
        "/summary/partials/sub_scope_dropdown.html",
        sub_scopes=sub_scopes,
        current_selected_sub_scopes=current_selected_sub_scopes,
    )


@module.route("/years", methods=["GET"])
@login_required
@with_user_context
def get_years():
    """HTMX endpoint: Load available years dropdown"""
    years = SummaryService.get_available_years(
        current_user.campus_id, current_user.department_key
    )

    # Get selected year from session to maintain state
    selected_year = SummarySessionManager.get_selected_year()

    return render_template(
        "/summary/partials/year_dropdown.html", years=years, selected_year=selected_year
    )


# ============================================================================
# SUB SCOPE POPUP (Modal for multi-select)
# ============================================================================


@module.route("/sub-scope-popup", methods=["GET"])
@login_required
@with_user_context
def sub_scope_popup():
    """HTMX endpoint: Show sub scope selection modal"""
    selected_scopes = request.args.getlist("selected_scopes")
    current_selected_sub_scopes = SummarySessionManager.get_selected_sub_scopes()

    sub_scopes = SummaryService.get_filtered_sub_scopes(
        current_user.campus_id,
        current_user.department_key,
        selected_scopes if selected_scopes else None,
    )

    return render_template(
        "/summary/partials/sub_scope_popup.html",
        sub_scopes=sub_scopes,
        current_selected_sub_scopes=current_selected_sub_scopes,
    )


@module.route("/toggle-sub-scope", methods=["POST"])
@login_required
@with_user_context
def toggle_sub_scope():
    """HTMX endpoint: Toggle sub scope selection in modal"""
    selected_scopes = request.form.getlist("selected_scopes")
    selected_sub_scopes = request.form.getlist("selected_sub_scopes")

    # Update session
    SummarySessionManager.set_selected_scopes(selected_scopes)
    SummarySessionManager.set_selected_sub_scopes(selected_sub_scopes)

    # Get filtered sub scopes for display
    sub_scopes = SummaryService.get_filtered_sub_scopes(
        current_user.campus_id,
        current_user.department_key,
        selected_scopes if selected_scopes else None,
    )

    return render_template(
        "/summary/partials/sub_scope_popup_content.html",
        sub_scopes=sub_scopes,
        current_selected_sub_scopes=selected_sub_scopes,
    )


@module.route("/select-all-sub-scopes", methods=["POST"])
@login_required
@with_user_context
def select_all_sub_scopes():
    """HTMX endpoint: Select all sub scopes in modal"""
    selected_scopes = request.form.getlist("selected_scopes")

    # Get all sub scopes for selected scopes
    sub_scopes = SummaryService.get_filtered_sub_scopes(
        current_user.campus_id,
        current_user.department_key,
        selected_scopes if selected_scopes else None,
    )

    # Select all
    selected_sub_scopes = [str(s.id) for s in sub_scopes]

    # Update session
    SummarySessionManager.set_selected_scopes(selected_scopes)
    SummarySessionManager.set_selected_sub_scopes(selected_sub_scopes)

    return render_template(
        "/summary/partials/sub_scope_popup_content.html",
        sub_scopes=sub_scopes,
        current_selected_sub_scopes=selected_sub_scopes,
    )


@module.route("/clear-all-sub-scopes", methods=["POST"])
@login_required
@with_user_context
def clear_all_sub_scopes():
    """HTMX endpoint: Clear all sub scope selections"""
    selected_scopes = request.form.getlist("selected_scopes")

    # Update session
    SummarySessionManager.set_selected_scopes(selected_scopes)
    SummarySessionManager.set_selected_sub_scopes([])

    # Get sub scopes for display
    sub_scopes = SummaryService.get_filtered_sub_scopes(
        current_user.campus_id,
        current_user.department_key,
        selected_scopes if selected_scopes else None,
    )

    return render_template(
        "/summary/partials/sub_scope_popup_content.html",
        sub_scopes=sub_scopes,
        current_selected_sub_scopes=[],
    )


# ============================================================================
# STATISTICS - HTMX Endpoints
# ============================================================================


@module.route("/stats", methods=["POST"])
@login_required
@with_user_context
def get_stats():
    """HTMX endpoint: Load statistics cards"""
    # Update session from form
    SummarySessionManager.update_from_form(request.form)

    # Get selected_year from form FIRST (for immediate update), then fallback to session
    selected_year_raw = request.form.get("selected_year")
    if selected_year_raw:
        try:
            selected_year = int(selected_year_raw)
            # Update session with the new year
            SummarySessionManager.set_selected_year(selected_year)
        except (TypeError, ValueError):
            selected_year = SummarySessionManager.get_selected_year()
    else:
        selected_year = SummarySessionManager.get_selected_year()

    # Get other filters from session
    filters = SummarySessionManager.get_all_filters()
    selected_scopes = filters["selected_scopes"]
    selected_sub_scopes = filters["selected_sub_scopes"]
    time_period = filters["time_period"]

    # Validate if no sub scopes selected
    if not selected_sub_scopes:
        return render_template("/summary/partials/stats_empty.html")

    # Validate sub scopes against selected scopes
    valid_sub_scopes = SummaryService.validate_sub_scopes(
        selected_sub_scopes,
        current_user.campus_id,
        current_user.department_key,
        selected_scopes if selected_scopes else None,
    )

    valid_ids = [str(s.id) for s in valid_sub_scopes]

    if not valid_ids:
        return render_template("/summary/partials/stats_empty.html")

    # Calculate emissions data
    data = SummaryService.calculate_emissions_data(
        current_user.campus_id,
        current_user.department_key,
        valid_ids,
        time_period,
        selected_year,
    )

    # Get unique scopes for display
    scopes = SummaryService.get_unique_scopes(
        current_user.campus_id, current_user.department_key
    )

    return render_template(
        "/summary/start_partial.html",
        data=data,
        time_period=time_period,
        scopes=scopes,
        selected_year=selected_year,
    )


@module.route("/clear-stats", methods=["POST"])
@login_required
def clear_stats():
    """HTMX endpoint: Show empty stats placeholder"""
    return render_template("/summary/partials/stats_empty.html")


# ============================================================================
# CHARTS - HTMX Endpoints
# ============================================================================


@module.route("/charts", methods=["POST"])
@login_required
@with_user_context
def get_charts():
    """HTMX endpoint: Load charts with multi-year data"""
    # Update session from form
    SummarySessionManager.update_from_form(request.form)

    # Get selected_year from form FIRST (for immediate update), then fallback to session
    selected_year_raw = request.form.get("selected_year")
    if selected_year_raw:
        try:
            selected_year = int(selected_year_raw)
            # Update session with the new year
            SummarySessionManager.set_selected_year(selected_year)
        except (TypeError, ValueError):
            selected_year = SummarySessionManager.get_selected_year()
    else:
        selected_year = SummarySessionManager.get_selected_year()

    # Get other filters from session
    filters = SummarySessionManager.get_all_filters()
    selected_scopes = filters["selected_scopes"]
    selected_sub_scopes = filters["selected_sub_scopes"]
    time_period = filters["time_period"]
    chart_time_range = request.form.get("chart_time_range", "1Y")

    # Validate if no sub scopes selected
    if not selected_sub_scopes:
        return render_template("/summary/partials/charts_empty.html")

    # Validate sub scopes
    valid_sub_scopes = SummaryService.validate_sub_scopes(
        selected_sub_scopes,
        current_user.campus_id,
        current_user.department_key,
        selected_scopes if selected_scopes else None,
    )

    valid_ids = [str(s.id) for s in valid_sub_scopes]

    if not valid_ids:
        return render_template("/summary/partials/charts_empty.html")

    chart_data = SummaryService.get_multi_year_data(
        current_user.campus_id,
        current_user.department_key,
        valid_ids,
        time_period,
        selected_year,
        chart_time_range,
    )

    return render_template(
        "/summary/charts_partial.html",
        data=chart_data["current_year_data"],
        previous_year_data=chart_data["previous_year_data"],
        multi_year_data=chart_data.get("multi_year_data", {}),
        selected_year=selected_year,
        chart_time_range=chart_time_range,
        year_range=chart_data.get("year_range", []),
    )


@module.route("/clear-charts", methods=["POST"])
@login_required
def clear_charts():
    """HTMX endpoint: Show empty charts placeholder"""
    return render_template("/summary/partials/charts_empty.html")


# ============================================================================
# TOP SUB SCOPES
# ============================================================================


@module.route("/partials/top_sub_scope", methods=["GET"])
@login_required
@with_user_context
def top_sub_scope_partial():
    """HTMX endpoint: Load top emitting sub scopes"""
    selected_scopes = request.args.getlist("selected_scope")
    selected_scope = request.args.get("selected_scope")
    selected_year = request.args.get("selected_year")

    # Parse selected year
    if selected_year:
        try:
            selected_year = int(selected_year)
        except (TypeError, ValueError):
            from datetime import datetime

            selected_year = datetime.now().year
    else:
        selected_year = SummarySessionManager.get_selected_year()

    # Determine scope filter
    scope_filter = None
    if selected_scope and selected_scope != "all":
        scope_filter = [int(selected_scope)]
    elif selected_scopes:
        scope_filter = [int(s) for s in selected_scopes if s.isdigit()]

    # Get top sub scopes
    top_materials, total_emissions = SummaryService.get_top_sub_scopes(
        current_user.campus_id,
        current_user.department_key,
        selected_year,
        scope_filter,
        limit=10,
    )

    # Get unique scopes for filter dropdown
    scopes = SummaryService.get_unique_scopes(
        current_user.campus_id, current_user.department_key
    )

    return render_template(
        "/summary/partials/top_sub_scope.html",
        scopes=scopes,
        top_materials=top_materials,
        selected_scope=(
            selected_scope
            if selected_scope == "all"
            else (
                int(selected_scope)
                if selected_scope and selected_scope.isdigit()
                else None
            )
        ),
        selected_year=selected_year,
        total_emissions=total_emissions,
    )


# ============================================================================
# BADGES - Active Filter Display
# ============================================================================


@module.route("/update-badges", methods=["GET", "POST"])
@login_required
@with_user_context
def update_badges():
    """HTMX endpoint: Update active filter badges"""
    selected_scopes = SummarySessionManager.get_selected_scopes()
    selected_sub_scopes = SummarySessionManager.get_selected_sub_scopes()

    sub_scope_objects = []
    if selected_sub_scopes:
        scope_object_ids = [ObjectId(x) for x in selected_sub_scopes]
        sub_scope_objects = list(
            Scope.objects(
                id__in=scope_object_ids,
                campus=current_user.campus_id,
                department=current_user.department_key,
            )
        )

        # Filter by selected scopes if applicable
        if selected_scopes:
            selected_scope_ints = [int(x) for x in selected_scopes]
            sub_scope_objects = [
                s for s in sub_scope_objects if s.ghg_scope in selected_scope_ints
            ]

    # Group badges by scope
    scope_badges = []
    if sub_scope_objects:
        from collections import defaultdict

        grouped = defaultdict(list)
        for sub_scope in sub_scope_objects:
            grouped[sub_scope.ghg_scope].append(sub_scope)

        for scope_num in sorted(grouped.keys()):
            scope_badges.append(
                {
                    "scope_number": scope_num,
                    "sub_scopes": sorted(
                        grouped[scope_num], key=lambda x: x.ghg_sup_scope
                    ),
                }
            )

    return render_template(
        "/summary/partials/active_badges.html",
        selected_scopes=selected_scopes,
        sub_scope_objects=sub_scope_objects,
        scope_badges=scope_badges,
        user=current_user,
    )


@module.route("/update-scope-selection", methods=["POST"])
@login_required
def update_scope_selection():
    """Update scope selection in session (AJAX endpoint)"""
    selected_scopes = request.form.getlist("selected_scopes")
    SummarySessionManager.set_selected_scopes(selected_scopes)
    return jsonify({"status": "success"})


# ============================================================================
# PDF EXPORT
# ============================================================================


@module.route("/download-pdf-modal", methods=["GET"])
@login_required
@permissions_required_all(["โหลดรายงานสรุปผล PDF"])
@with_user_context
def download_pdf_modal():
    """HTMX endpoint: Show PDF download modal"""
    selected_year = request.args.get("selected_year")
    if selected_year:
        try:
            selected_year = int(selected_year)
        except (TypeError, ValueError):
            selected_year = SummarySessionManager.get_selected_year()
    else:
        selected_year = SummarySessionManager.get_selected_year()

    return render_template(
        "/summary/partials/download_pdf_modal.html",
        user=current_user,
        selected_year=selected_year,
    )


@module.route("/preview-pdf-modal", methods=["GET"])
@login_required
@permissions_required_all(["ดูตัวอย่างสรุปผล PDF"])
@with_user_context
def preview_pdf_modal():
    """HTMX endpoint: Show PDF preview modal"""
    # Get filter parameters
    selected_year = request.args.get("selected_year")
    if selected_year:
        try:
            selected_year = int(selected_year)
        except (TypeError, ValueError):
            selected_year = SummarySessionManager.get_selected_year()
    else:
        selected_year = SummarySessionManager.get_selected_year()

    time_period = request.args.get("time_period", "week")
    selected_scopes = request.args.getlist("selected_scopes")
    selected_sub_scopes = request.args.getlist("selected_sub_scopes")

    # Fallback to session
    if not selected_scopes:
        selected_scopes = SummarySessionManager.get_selected_scopes()
    if not selected_sub_scopes:
        selected_sub_scopes = SummarySessionManager.get_selected_sub_scopes()

    # If no sub scopes, return empty data
    if not selected_sub_scopes:
        data = {
            "total_emissions": 0,
            "daily_average": 0,
            "daily_data": {},
            "category_data": {},
            "scope_data": {},
        }
        last_year_data = {"daily_data": {}}
        bar_chart_base64 = ""
        last_year_bar_chart_base64 = ""
        category_chart_base64 = ""
        scope_emissions = []
        scope_breakdown_table = []
    else:
        # Validate sub scopes
        valid_sub_scopes = SummaryService.validate_sub_scopes(
            selected_sub_scopes,
            current_user.campus_id,
            current_user.department_key,
            selected_scopes if selected_scopes else None,
        )

        valid_ids = [str(s.id) for s in valid_sub_scopes]

        # Calculate data
        data = SummaryService.calculate_emissions_data(
            current_user.campus_id,
            current_user.department_key,
            valid_ids,
            time_period,
            selected_year,
        )

        last_year_data = SummaryService.calculate_emissions_data(
            current_user.campus_id,
            current_user.department_key,
            valid_ids,
            time_period,
            selected_year - 1,
        )

        # Generate charts
        bar_chart_base64 = ChartGenerator.generate_bar_chart(
            data["daily_data"], last_year_data["daily_data"], selected_year
        )

        last_year_bar_chart_base64 = ChartGenerator.generate_bar_chart(
            last_year_data["daily_data"], None, selected_year - 1
        )

        category_chart_base64 = ChartGenerator.generate_donut_chart(
            data["category_data"]
        )

        # Prepare scope emissions and breakdown
        scope_emissions = [
            {
                "scope_name": key,
                "emissions": value["emissions"],
                "percentage": (
                    (value["emissions"] / data["total_emissions"] * 100)
                    if data["total_emissions"] > 0
                    else 0
                ),
            }
            for key, value in data["scope_data"].items()
        ]

        scope_breakdown_table = [
            {
                "scope_name": value["ghg_name"],
                "emissions": value["emissions"],
                "percentage": (
                    (value["emissions"] / data["total_emissions"] * 100)
                    if data["total_emissions"] > 0
                    else 0
                ),
            }
            for value in data["scope_data"].values()
        ]

    return render_template(
        "/summary/partials/preview_pdf_modal.html",
        user=current_user,
        selected_year=selected_year,
        data=data,
        last_year_data=last_year_data,
        bar_chart_base64=bar_chart_base64,
        last_year_bar_chart_base64=last_year_bar_chart_base64,
        category_chart_base64=category_chart_base64,
        scope_emissions=scope_emissions,
        scope_breakdown_table=scope_breakdown_table,
    )


@module.route("/download-pdf", methods=["POST"])
@login_required
@permissions_required_all(["โหลดรายงานสรุปผล PDF"])
@with_user_context
def download_pdf():
    """
    Generate and download PDF report
    Note: PDF generation logic remains complex and is kept here
    Consider extracting to a separate PDF service if needed
    """
    # TODO: Implement PDF generation using reportlab
    # This should use SummaryService for data and ChartGenerator for charts
    # For now, return error
    return (
        jsonify(
            {
                "status": "error",
                "message": "PDF generation not yet implemented in refactored version",
            }
        ),
        501,
    )
