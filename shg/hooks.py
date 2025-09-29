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

# Register workspace components
desk_pages = [
    {
        "module_name": "SHG",
        "workspace_name": "SHG",
        "parent": "Workspace",
        "idx": 1,
        "icon": "organization",
        "label": "SHG",
        "restrict_to_domain": "",
        "link_to": "",
        "type": "Workspace",
        "public": 1
    }
]

# Register number cards
number_cards = [
    {
        "module_name": "SHG",
        "name": "Active Members",
        "label": "Active Members",
        "doctype": "Number Card"
    },
    {
        "module_name": "SHG",
        "name": "Monthly Contributions",
        "label": "Monthly Contributions",
        "doctype": "Number Card"
    },
    {
        "module_name": "SHG",
        "name": "Outstanding Loans",
        "label": "Outstanding Loans",
        "doctype": "Number Card"
    },
    {
        "module_name": "SHG",
        "name": "Upcoming Meetings",
        "label": "Upcoming Meetings",
        "doctype": "Number Card"
    }
]

# Register dashboard charts
dashboard_charts = [
    {
        "module_name": "SHG",
        "name": "Members Overview",
        "label": "Members Overview",
        "doctype": "Dashboard Chart"
    },
    {
        "module_name": "SHG",
        "name": "Financial Summary",
        "label": "Financial Summary",
        "doctype": "Dashboard Chart"
    }
]

# Register workspace cards
workspace_cards = [
    {
        "module_name": "SHG",
        "name": "Member Management",
        "label": "Member Management",
        "doctype": "Workspace Card"
    },
    {
        "module_name": "SHG",
        "name": "Financial Management",
        "label": "Financial Management",
        "doctype": "Workspace Card"
    },
    {
        "module_name": "SHG",
        "name": "Meeting Management",
        "label": "Meeting Management",
        "doctype": "Workspace Card"
    },
    {
        "module_name": "SHG",
        "name": "Reports & Analytics",
        "label": "Reports & Analytics",
        "doctype": "Workspace Card"
    },
    {
        "module_name": "SHG",
        "name": "Settings",
        "label": "Settings",
        "doctype": "Workspace Card"
    }
]