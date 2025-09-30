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
        "validate": "shg.shg.doctype.shg_member.shg_member.validate_member",
        "on_submit": "shg.shg.doctype.shg_member.shg_member.create_member_ledger"
    },
    "SHG Contribution": {
        "validate": "shg.shg.doctype.shg_contribution.shg_contribution.validate_contribution",
        "on_submit": "shg.shg.doctype.shg_contribution.shg_contribution.post_to_general_ledger"
    },
    "SHG Loan": {
        "validate": "shg.shg.doctype.shg_loan.shg_loan.validate_loan",
        "on_submit": "shg.shg.doctype.shg_loan.shg_loan.generate_repayment_schedule"
    }
}

# Scheduled Tasks
scheduler_events = {
    "daily": [
        "shg.tasks.send_daily_reminders",
        "shg.tasks.calculate_loan_penalties"
    ],
    "weekly": [
        "shg.tasks.send_weekly_contribution_reminders"
    ],
    "monthly": [
        "shg.tasks.generate_monthly_reports"
    ]
}

# Installation
after_install = "shg.install.after_install"

# Custom Fields
custom_fields = {
    "Customer": [
        {
            "fieldname": "is_shg_member",
            "label": "Is SHG Member", 
            "fieldtype": "Check",
            "insert_after": "customer_type"
        },
        {
            "fieldname": "shg_member_id",
            "label": "SHG Member ID",
            "fieldtype": "Data",
            "insert_after": "is_shg_member",
            "depends_on": "is_shg_member"
        }
    ]
}

# DocType JS
doctype_js = {
    "SHG Member": "public/js/shg_member.js",
    "SHG Contribution": "public/js/shg_contribution.js",
    "SHG Loan": "public/js/shg_loan.js",
    "SHG Meeting": "public/js/shg_meeting.js"
}

# Fix for workspace path issue
app_include_js = "/assets/shg/js/shg.js"
app_include_css = "/assets/shg/css/shg.css"

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