"""
User Context Decorator - Eliminates code duplication
Automatically enriches current_user with campus and department names
"""

from functools import wraps
from flask_login import current_user
from ...models import CampusAndDepartment


def with_user_context(f):
    """
    Decorator that enriches current_user with campus and department information

    Usage:
        @module.route("/endpoint")
        @login_required
        @with_user_context
        def my_endpoint():
            # current_user now has .campus and .department attributes
            print(current_user.campus)  # Campus name string
            print(current_user.department)  # Department name string
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Enrich current_user with campus and department names
        if hasattr(current_user, "campus_id") and hasattr(
            current_user, "department_key"
        ):
            current_user.campus = CampusAndDepartment.get_campus_name(
                current_user.campus_id
            )
            current_user.department = CampusAndDepartment.get_department_name(
                current_user.campus_id, current_user.department_key
            )

        return f(*args, **kwargs)

    return decorated_function


def get_user_context_dict():
    """
    Get user context as a dictionary for passing to templates

    Returns:
        dict: Contains user, campus_id, department_key, campus, department
    """
    if not hasattr(current_user, "campus_id"):
        return {}

    return {
        "user": current_user,
        "campus_id": current_user.campus_id,
        "department_key": current_user.department_key,
        "campus": CampusAndDepartment.get_campus_name(current_user.campus_id),
        "department": CampusAndDepartment.get_department_name(
            current_user.campus_id, current_user.department_key
        ),
    }
