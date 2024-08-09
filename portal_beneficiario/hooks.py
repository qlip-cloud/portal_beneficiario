from . import __version__ as app_version

app_name = "portal_beneficiario"
app_title = "Portal Beneficiario"
app_publisher = "Adolfo Hernandez"
app_description = "Portal de Beneficiario"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "adolfo.jgi.hernandez@gmail.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/portal_beneficiario/css/portal_beneficiario.css"
# app_include_js = "/assets/portal_beneficiario/js/portal_beneficiario.js"

# include js, css files in header of web template
# web_include_css = "/assets/portal_beneficiario/css/portal_beneficiario.css"
# web_include_js = "/assets/portal_beneficiario/js/portal_beneficiario.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "portal_beneficiario/public/scss/website"

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
#home_page = "home/index"

#base_template = "portal_beneficiario/templates/pb_base.html"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "portal_beneficiario.install.before_install"
# after_install = "portal_beneficiario.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "portal_beneficiario.notifications.get_notification_config"

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
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
#	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"portal_beneficiario.tasks.all"
# 	],
# 	"daily": [
# 		"portal_beneficiario.tasks.daily"
# 	],
# 	"hourly": [
# 		"portal_beneficiario.tasks.hourly"
# 	],
# 	"weekly": [
# 		"portal_beneficiario.tasks.weekly"
# 	]
# 	"monthly": [
# 		"portal_beneficiario.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "portal_beneficiario.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "portal_beneficiario.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "portal_beneficiario.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]


# User Data Protection
# --------------------

user_data_fields = [
	{
		"doctype": "{doctype_1}",
		"filter_by": "{filter_by}",
		"redact_fields": ["{field_1}", "{field_2}"],
		"partial": 1,
	},
	{
		"doctype": "{doctype_2}",
		"filter_by": "{filter_by}",
		"partial": 1,
	},
	{
		"doctype": "{doctype_3}",
		"strict": False,
	},
	{
		"doctype": "{doctype_4}"
	}
]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"portal_beneficiario.auth.validate"
# ]

fixtures = [
    # export all records from the Category table
	"qp_PO_BusinessActivity",
	"qp_PO_City",
	"qp_PO_DocumentType",
	"qp_PO_EconomicActivity",
	"qp_PO_Nationality",
    "qp_PO_Positions",
    "qp_PO_SourceFund",
    "qp_PO_ParentType" 
]

# get_website_user_home_page = "app.website.get_home_page"
get_website_user_home_page = "portal_beneficiario.portal_beneficiario.uses_cases.login.redirects.get_home_page"

website_redirects = [
    {"source": "/login", "target": "/login_pb"},
]