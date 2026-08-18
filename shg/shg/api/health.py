"""
Health-check endpoint for the SHG app.

This can be used by load balancers, monitoring tools, or mobile clients to
confirm that the app is installed and that critical services are reachable.
"""
import frappe
from frappe import _

from shg.shg.utils.api_utils import error_response, success_response


@frappe.whitelist(allow_guest=True)
def health():
    """Return SHG app health status.

    Checks:
    - Database connectivity
    - Scheduler status
    - SHG Settings existence
    - Optional M-Pesa and SMS configuration completeness
    """
    try:
        # DB connectivity
        frappe.db.sql("SELECT 1")

        scheduler_enabled = frappe.utils.scheduler.is_scheduler_enabled()

        settings = frappe.get_doc("SHG Settings")
        has_settings = bool(settings.name)

        mpesa_configured = bool(
            settings.get("mpesa_enabled")
            and settings.get("mpesa_consumer_key")
            and settings.get("mpesa_shortcode")
            and settings.get("mpesa_passkey")
        )
        sms_configured = bool(
            settings.get("sms_enabled") and settings.get("sms_api_key") and settings.get("sms_username")
        )

        return success_response(
            data={
                "app": "shg",
                "version": frappe.get_cached_value("Installed Application", {"app_name": "shg"}, "app_version") or "unknown",
                "database": True,
                "scheduler_enabled": scheduler_enabled,
                "settings_configured": has_settings,
                "mpesa_configured": mpesa_configured,
                "sms_configured": sms_configured,
                "timestamp": frappe.utils.now(),
            },
            message=_("SHG app is healthy"),
        )
    except Exception as e:
        return error_response(
            message=str(e),
            error_code="HEALTH_CHECK_FAILED",
            status_code=503,
        )
