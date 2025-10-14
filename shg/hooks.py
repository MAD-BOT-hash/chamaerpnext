from . import __version__ as app_version

app_name = "shg"
app_title = "Self Help Group Management"
app_publisher = "SHG Solutions"
app_description = "Complete SHG management system for Kenya"
app_icon = "octicon octicon-organization"
app_color = "green"
app_email = "support@shgsolutions.co.ke"
app_license = "MIT"

# Document Events
doc_events = {
    "SHG Member": {
        "validate": "shg.install.validate_member",
        "on_submit": "shg.install.create_member_ledger",
        "on_amend": "shg.shg.doctype.shg_member.shg_member.handle_member_amendment",
        "on_update_after_submit": "shg.shg.doctype.shg_member.shg_member.handle_member_update_after_submit"
    },
    "SHG Contribution": {
        "validate": "shg.shg.doctype.shg_contribution.shg_contribution.validate_contribution",
        "on_submit": "shg.shg.doctype.shg_contribution.shg_contribution.post_to_general_ledger"
    },
    "SHG Contribution Invoice": {
        "validate": "shg.shg.doctype.shg_contribution_invoice.shg_contribution_invoice.validate_contribution_invoice"
    },
    "SHG Loan": {
        "validate": "shg.shg.doctype.shg_loan.shg_loan.validate_loan",
        "on_submit": "shg.shg.doctype.shg_loan.shg_loan.post_to_general_ledger"
    },
    "SHG Loan Repayment": {
        "validate": "shg.shg.doctype.shg_loan_repayment.shg_loan_repayment.validate_repayment",
        "on_submit": "shg.shg.doctype.shg_loan_repayment.shg_loan_repayment.post_to_general_ledger"
    },
    "SHG Meeting Fine": {
        "validate": "shg.shg.doctype.shg_meeting_fine.shg_meeting_fine.validate_fine",
        "on_submit": "shg.shg.doctype.shg_meeting_fine.shg_meeting_fine.post_to_general_ledger"
    },
    "Payment Entry": {
        "validate": "shg.shg.hooks.payment_entry.payment_entry_validate",
        "on_submit": "shg.shg.hooks.payment_entry.payment_entry_on_submit"
    }
}

# Scheduled Tasks
scheduler_events = {
    "daily": [
        "shg.tasks.send_daily_reminders",
        "shg.tasks.calculate_loan_penalties",
        "shg.tasks.generate_billable_contribution_invoices",
        "shg.shg.doctype.shg_contribution.shg_contribution.update_overdue_contributions"
    ],
    "weekly": [
        "shg.tasks.send_weekly_contribution_reminders"
    ],
    "monthly": [
        "shg.tasks.generate_monthly_reports",
        "shg.utils.email.send_monthly_statements",
        "shg.utils.whatsapp.send_monthly_statements_whatsapp",
        "shg.tasks.send_monthly_member_statements"
    ]
}

# Installation
after_install = "shg.install.after_install"

# DocType JS
doctype_js = {
    "SHG Member": "public/js/shg_member.js",
    "SHG Contribution": "public/js/shg_contribution.js",
    "SHG Loan": "public/js/shg_loan.js",
    "SHG Meeting": "public/js/shg_meeting.js",
    "SHG Member Attendance": "public/js/shg_member_attendance.js",
    "SHG Settings": "public/js/shg_settings.js",
    "SHG Contribution Invoice": "public/js/shg_contribution_invoice.js",
    "SHG Payment Entry": "shg/doctype/shg_payment_entry/shg_payment_entry.js"
}

# List JS
doctype_list_js = {
    "SHG Payment Entry": "public/js/shg_payment_entry_list.js"
}

# Fix for workspace path issue
app_include_js = ["/assets/shg/js/shg.js", "/assets/shg/js/shg_dashboard.js"]
app_include_css = ["/assets/shg/css/shg.css", "/assets/shg/css/shg_dashboard.css"]

# Page extensions
has_website_permission = {
    "SHG Dashboard": "shg.shg.page.shg_dashboard.shg_dashboard.has_website_permission"
}

# API endpoints
website_route_rules = [
    {"from_route": "/api/method/shg.api.login", "to_route": "shg.api.login"},
    {"from_route": "/api/method/shg.api.get_member_statement", "to_route": "shg.api.get_member_statement"},
    {"from_route": "/api/method/shg.api.submit_contribution", "to_route": "shg.api.submit_contribution"},
    {"from_route": "/api/method/shg.api.apply_loan", "to_route": "shg.api.apply_loan"},
    {"from_route": "/api/method/shg.api.get_notifications", "to_route": "shg.api.get_notifications"},
    {"from_route": "/api/method/shg.api.get_upcoming_meetings", "to_route": "shg.api.get_upcoming_meetings"},
    {"from_route": "/api/method/shg.api.get_member_profile", "to_route": "shg.api.get_member_profile"}
]