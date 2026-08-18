"""
Standardized API response helpers for SHG mobile/web API.

All whitelisted API methods should return a consistent envelope so that
clients can rely on the same shape for success and error cases.
"""
from typing import Any, Dict, Optional

import frappe


def success_response(
    data: Any = None,
    message: str = "",
    status_code: int = 200,
) -> Dict[str, Any]:
    """Return a standardized success envelope."""
    response = {
        "success": True,
        "data": data,
        "error": None,
    }
    if message:
        response["message"] = message
    frappe.local.response.http_status_code = status_code
    return response


def error_response(
    message: str,
    error_code: str = "",
    status_code: int = 400,
    details: Optional[Any] = None,
) -> Dict[str, Any]:
    """Return a standardized error envelope and log the error."""
    frappe.log_error(title=f"SHG API Error: {error_code or 'GENERAL'}", message=message)
    response = {
        "success": False,
        "data": None,
        "error": {
            "code": error_code or "GENERAL_ERROR",
            "message": message,
            "details": details,
        },
    }
    frappe.local.response.http_status_code = status_code
    return response


def validation_error(field: str, message: str) -> Dict[str, Any]:
    """Return a standardized validation error envelope."""
    return error_response(
        message=message,
        error_code="VALIDATION_ERROR",
        status_code=422,
        details={"field": field},
    )


def require_json_params(*params: str) -> None:
    """Ensure that the JSON body contains all required parameters.

    Raises frappe.ValidationError if any parameter is missing.
    """
    data = frappe.request.get_json(silent=True) or {}
    missing = [p for p in params if p not in data or data[p] in (None, "")]
    if missing:
        frappe.throw(
            frappe._("Missing required parameter(s): {0}").format(", ".join(missing)),
            title=frappe._("Validation Error"),
        )


def get_json_param(name: str, default: Any = None, required: bool = False) -> Any:
    """Read a parameter from the JSON request body."""
    data = frappe.request.get_json(silent=True) or {}
    value = data.get(name, default)
    if required and value in (None, ""):
        frappe.throw(
            frappe._("Missing required parameter: {0}").format(name),
            title=frappe._("Validation Error"),
        )
    return value
