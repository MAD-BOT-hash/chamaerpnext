"""
Hooks for SHG Loan module
"""
from . import __version__ as app_version

app_name = "shg"
app_title = "SHG"
app_publisher = "SHG"
app_description = "Self Help Group Management System"
app_email = "info@shg.org"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/shg/css/shg.css"
# app_include_js = "/assets/shg/js/shg.js"

# include js, css files in header of web template
# web_include_css = "/assets/shg/css/shg.css"
# web_include_js = "/assets/shg/js/shg.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "shg/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "shg.utils.jinja_methods",
# 	"filters": "shg.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "shg.install.before_install"
# after_install = "shg.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "shg.uninstall.before_uninstall"
# after_uninstall = "shg.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# see other apps for notifications
# notification_config = "shg.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "SHG Loan": {
        "on_submit": [
            "shg.shg.loan_services.gl.post_loan_disbursement"
        ],
        "on_update": [
            "shg.shg.loan_services.schedule.generate_schedule_for_loan"
        ]
    },
    "SHG Loan Repayment": {
        "on_submit": [
            "shg.shg.loan_services.allocation.handle_loan_repayment_submission"
        ]
    },
    "GL Entry": {
        "on_submit": [
            "shg.shg.loan_services.gl.create_repayment_gl_entries"
        ]
    }
}

# Scheduled Tasks
# ---------------

scheduler_events = {
    "daily": [
        "shg.shg.loan_services.accrual.process_daily_accruals"
    ],
    "monthly": [
        "shg.shg.loan_services.report.generate_monthly_report"
    ]
}

# Testing
# -------

# before_tests = "shg.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "shg.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "shg.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["shg.utils.before_request"]
# after_request = ["shg.utils.after_request"]

# Job Events
# ----------
# before_job = ["shg.utils.before_job"]
# after_job = ["shg.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"shg.auth.validate"
# ]