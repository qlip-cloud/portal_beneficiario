from . import __version__ as app_version

app_name = "portal_beneficiario"
app_title = "Portal Beneficiario"
app_publisher = "Adolfo Hernandez"
app_description = "Portal de Beneficiario"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "adolfo.jgi.hernandez@gmail.com"
app_license = "MIT"

# Permissions
# -----------
# Restringe a los Website User estrictamente a lectura/escritura sobre su propio qp_PO_Beneficiario
permission_query_conditions = {
	"qp_PO_Beneficiario": "portal_beneficiario.portal_beneficiario.services.beneficiary.get_beneficiary_permission_query_conditions",
}

has_permission = {
	"qp_PO_Beneficiario": "portal_beneficiario.portal_beneficiario.services.beneficiary.has_beneficiary_permission",
}

# Document Events
# ---------------
# Validación server-side de archivos adjuntos a qp_PO_Beneficiario
doc_events = {
	"File": {
		"validate": "portal_beneficiario.portal_beneficiario.services.beneficiary.validate_beneficiary_file"
	}
}

# User Data Protection (Ley 1581 / GDPR)
# --------------------------------------
user_data_fields = [
	{
		"doctype": "qp_PO_Beneficiario",
		"filter_by": "email",
		"redact_fields": [
			"phone",
			"address",
			"document_number",
			"birthday",
			"income",
			"egress",
			"assets",
			"passive",
			"account_number",
			"parent_name",
			"jumio_file",
			"jumio_iframe",
		],
		"partial": 1,
	}
]

website_redirects = [
	{"source": "/login", "target": "/login-qlip"},
]

fixtures = [
	# Solo catálogos maestros públicos (no incluir nunca DocTypes de credenciales ni datos de beneficiarios)
	"qp_PO_BusinessActivity",
	"qp_PO_City",
	"qp_PO_EconomicActivity",
	"qp_PO_Nationality",
	"qp_PO_Positions",
	"qp_PO_SourceFund",
	"qp_PO_ParentType",
	"qp_PO_AccountType",
]

get_website_user_home_page = "portal_beneficiario.portal_beneficiario.uses_cases.login.redirects.get_home_page"