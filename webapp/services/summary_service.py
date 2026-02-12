"""
Summary Service - Business Logic Layer
Handles all emissions calculations and data aggregation
"""

from datetime import datetime
from bson import ObjectId
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

from ..models import Scope, CampusAndDepartment
from ..models.materail_model import Material


class SummaryService:
    """Service for handling summary dashboard business logic"""

    MONTH_NAMES = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]

    @staticmethod
    def get_unique_scopes(campus_id: str, department_key: str) -> List[Scope]:
        """Get unique scopes (by ghg_scope number) for a campus/department"""
        all_scopes = Scope.objects(campus=campus_id, department=department_key)
        seen = set()
        unique_scopes = []
        for scope in all_scopes:
            if scope.ghg_scope not in seen:
                seen.add(scope.ghg_scope)
                unique_scopes.append(scope)
        return unique_scopes

    @staticmethod
    def get_filtered_sub_scopes(
        campus_id: str,
        department_key: str,
        selected_scope_ids: Optional[List[int]] = None,
    ) -> List[Scope]:
        """Get sub scopes filtered by selected scope IDs"""
        query = {"campus": campus_id, "department": department_key}

        if selected_scope_ids:
            query["ghg_scope__in"] = [int(sid) for sid in selected_scope_ids]

        return Scope.objects(**query).order_by("ghg_scope", "ghg_sup_scope")

    @staticmethod
    def get_available_years(campus_id: str, department_key: str) -> List[int]:
        """Get all years that have materials data"""
        materials = Material.objects(campus=campus_id, department=department_key)
        years = sorted(list(set([m.year for m in materials if m.year])))
        return years if years else [datetime.now().year]

    @staticmethod
    def validate_sub_scopes(
        sub_scope_ids: List[str],
        campus_id: str,
        department_key: str,
        selected_scope_ids: Optional[List[str]] = None,
    ) -> List[Scope]:
        """Validate and filter sub scopes based on selected scopes"""
        scope_object_ids = [ObjectId(x) for x in sub_scope_ids]
        all_selected_sub_scopes = Scope.objects(
            id__in=scope_object_ids, campus=campus_id, department=department_key
        )

        if selected_scope_ids:
            selected_scope_ints = [int(x) for x in selected_scope_ids]
            valid_sub_scopes = [
                s for s in all_selected_sub_scopes if s.ghg_scope in selected_scope_ints
            ]
        else:
            valid_sub_scopes = list(all_selected_sub_scopes)

        return valid_sub_scopes

    @staticmethod
    def calculate_emissions_data(
        campus_id: str,
        department_key: str,
        sub_scope_ids: List[str],
        time_period: str = "week",
        selected_year: Optional[int] = None,
    ) -> Dict:
        """
        Calculate emissions data for given sub scopes and year

        Returns:
            dict with keys: total_emissions, daily_average, average_label,
            year_change_percent, year_change_trend, last_year_total,
            daily_data, category_data, materials_count, scope_data
        """
        if not selected_year:
            selected_year = datetime.now().year

        # Convert sub_scope IDs to scope objects
        scope_object_ids = [ObjectId(scope_id) for scope_id in sub_scope_ids]
        scopes = Scope.objects(
            id__in=scope_object_ids, campus=campus_id, department=department_key
        )

        # Get unique scope pairs (ghg_scope, ghg_sup_scope)
        scope_pairs = list(
            set([(scope.ghg_scope, scope.ghg_sup_scope) for scope in scopes])
        )

        # Fetch current year materials
        materials_list = []
        for ghg_scope, ghg_sup_scope in scope_pairs:
            materials_for_scope = Material.objects(
                campus=campus_id,
                department=department_key,
                scope=ghg_scope,
                sub_scope=ghg_sup_scope,
                year=int(selected_year),
            )
            materials_list.extend(materials_for_scope)

        # Deduplicate materials
        unique_materials = {}
        for material in materials_list:
            material_id = str(material.id)
            if material_id not in unique_materials:
                unique_materials[material_id] = material
        materials_list = list(unique_materials.values())

        # Fetch last year materials
        last_year_materials_list = []
        for ghg_scope, ghg_sup_scope in scope_pairs:
            last_year_materials = Material.objects(
                campus=campus_id,
                department=department_key,
                scope=ghg_scope,
                sub_scope=ghg_sup_scope,
                year=int(selected_year) - 1,
            )
            last_year_materials_list.extend(last_year_materials)

        # Deduplicate last year materials
        unique_last_year = {}
        for material in last_year_materials_list:
            material_id = str(material.id)
            if material_id not in unique_last_year:
                unique_last_year[material_id] = material
        last_year_materials_list = list(unique_last_year.values())

        # Calculate monthly data
        daily_data = {month: 0 for month in SummaryService.MONTH_NAMES}
        for material in materials_list:
            if material.month and 1 <= material.month <= 12:
                month_name = SummaryService.MONTH_NAMES[material.month - 1]
                daily_data[month_name] += material.result2 or 0

        # Calculate category data (Scope 1, 2, 3 totals)
        category_data = {}
        scope_data = {}

        for ghg_scope, ghg_sup_scope in scope_pairs:
            scope_name = f"Scope {ghg_scope}"

            scope_materials = [
                m
                for m in materials_list
                if m.scope == ghg_scope and m.sub_scope == ghg_sup_scope
            ]
            emissions = sum(m.result2 or 0 for m in scope_materials)

            category_data[scope_name] = category_data.get(scope_name, 0) + emissions

            scope_key = f"Scope {ghg_scope}.{ghg_sup_scope}"
            scope_object = next(
                (
                    s
                    for s in scopes
                    if s.ghg_scope == ghg_scope and s.ghg_sup_scope == ghg_sup_scope
                ),
                None,
            )

            scope_data[scope_key] = {
                "ghg_scope": ghg_scope,
                "ghg_sup_scope": ghg_sup_scope,
                "emissions": emissions,
                "scope_object": scope_object,
                "ghg_name": (
                    scope_object.ghg_name
                    if scope_object
                    else f"Scope {ghg_scope}.{ghg_sup_scope}"
                ),
            }

        # Calculate totals and changes
        current_year_total = sum(m.result2 or 0 for m in materials_list)
        last_year_total = sum(m.result2 or 0 for m in last_year_materials_list)

        if last_year_total > 0:
            year_change_percent = (
                (current_year_total - last_year_total) / last_year_total
            ) * 100
        else:
            year_change_percent = 100 if current_year_total > 0 else 0

        # Calculate averages based on time period
        time_period_config = {
            "Day": (365, "Per Day"),
            "week": (52, "Per Week"),
            "month": (12, "Per Month"),
        }
        divisor, label = time_period_config.get(time_period, (365, "Per Day"))
        daily_average = current_year_total / divisor

        return {
            "total_emissions": round(current_year_total, 2),
            "daily_average": round(daily_average, 2),
            "average_label": label,
            "year_change_percent": round(year_change_percent, 1),
            "year_change_trend": (
                "increase"
                if year_change_percent > 0
                else "decrease" if year_change_percent < 0 else "stable"
            ),
            "last_year_total": round(last_year_total, 2),
            "daily_data": daily_data,
            "category_data": category_data,
            "materials_count": len(materials_list),
            "scope_data": scope_data,
            "selected_year": selected_year,
        }

    @staticmethod
    def get_multi_year_data(
        campus_id: str,
        department_key: str,
        sub_scope_ids: List[str],
        time_period: str,
        selected_year: int,
        chart_time_range: str,
    ) -> Dict:
        """Get emissions data for multiple years based on time range"""
        # Determine year range
        if chart_time_range == "1Y":
            year_range = [selected_year]
        elif chart_time_range == "5Y":
            year_range = list(range(selected_year - 4, selected_year + 1))
        elif chart_time_range == "10Y":
            year_range = list(range(selected_year - 9, selected_year + 1))
        elif chart_time_range == "ALL":
            # Get all available years from materials
            scope_object_ids = [ObjectId(scope_id) for scope_id in sub_scope_ids]
            scopes = Scope.objects(
                id__in=scope_object_ids, campus=campus_id, department=department_key
            )
            scope_pairs = list(
                set([(scope.ghg_scope, scope.ghg_sup_scope) for scope in scopes])
            )

            all_years = set()
            for ghg_scope, ghg_sup_scope in scope_pairs:
                materials = Material.objects(
                    campus=campus_id,
                    department=department_key,
                    scope=ghg_scope,
                    sub_scope=ghg_sup_scope,
                )
                all_years.update([m.year for m in materials if m.year])

            year_range = sorted(list(all_years)) if all_years else [selected_year]
        else:
            year_range = [selected_year]

        # Get data for current and previous year
        current_year_data = SummaryService.calculate_emissions_data(
            campus_id, department_key, sub_scope_ids, time_period, selected_year
        )
        previous_year_data = SummaryService.calculate_emissions_data(
            campus_id, department_key, sub_scope_ids, time_period, selected_year - 1
        )

        # Get data for all years in range
        multi_year_data = {}
        for year in year_range:
            year_data = SummaryService.calculate_emissions_data(
                campus_id, department_key, sub_scope_ids, time_period, year
            )
            multi_year_data[year] = year_data["daily_data"]

        return {
            "current_year_data": current_year_data,
            "previous_year_data": previous_year_data,
            "multi_year_data": multi_year_data,
            "year_range": year_range,
        }

    @staticmethod
    def get_top_sub_scopes(
        campus_id: str,
        department_key: str,
        selected_year: int,
        selected_scope_ids: Optional[List[int]] = None,
        limit: int = 10,
    ) -> Tuple[List[Dict], float]:
        """
        Get top emitting sub scopes

        Returns:
            Tuple of (top_materials_list, total_emissions)
        """
        query = {
            "campus": campus_id,
            "department": department_key,
            "year": int(selected_year),
        }

        if selected_scope_ids and "all" not in [str(s) for s in selected_scope_ids]:
            query["scope__in"] = [int(s) for s in selected_scope_ids]

        materials = Material.objects(**query)

        # Group by sub scope
        sub_scope_emissions = defaultdict(lambda: {"emissions": 0, "materials": []})

        for material in materials:
            key = (material.scope, material.sub_scope)
            sub_scope_emissions[key]["emissions"] += material.result2 or 0
            sub_scope_emissions[key]["materials"].append(material)

        # Sort by emissions and get top N
        sorted_sub_scopes = sorted(
            sub_scope_emissions.items(), key=lambda x: x[1]["emissions"], reverse=True
        )[:limit]

        # Build result
        top_materials = []
        total_emissions = 0

        for (scope_num, sub_scope_num), data in sorted_sub_scopes:
            scope_obj = Scope.objects(
                campus=campus_id,
                department=department_key,
                ghg_scope=scope_num,
                ghg_sup_scope=sub_scope_num,
            ).first()

            emissions = data["emissions"]
            total_emissions += emissions

            top_materials.append(
                {
                    "scope": scope_num,
                    "sub_scope": sub_scope_num,
                    "scope_name": (
                        scope_obj.ghg_name
                        if scope_obj
                        else f"Scope {scope_num}.{sub_scope_num}"
                    ),
                    "emissions": round(emissions, 2),
                    "percentage": 0,  # Will calculate after total is known
                }
            )

        # Calculate percentages
        if total_emissions > 0:
            for item in top_materials:
                item["percentage"] = round(
                    (item["emissions"] / total_emissions) * 100, 1
                )

        return top_materials, round(total_emissions, 2)
