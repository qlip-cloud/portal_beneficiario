import frappe
import os, re
import json
from frappe import _
import frappe.sessions
from six import string_types
from frappe.utils import getdate


def get_context(context):

    if frappe.session.user == "Guest":
        frappe.throw(_("Log in to access this page."), frappe.PermissionError)

    try:
        boot = frappe.sessions.get()
    except Exception as e:
        boot = frappe._dict(status='failed', error = str(e))
        print(frappe.get_traceback())

	# this needs commit
    csrf_token = frappe.sessions.get_csrf_token()
    frappe.db.commit()

    boot_json = frappe.as_json(boot)

    # remove script tags from boot
    boot_json = re.sub(r"\<script[^<]*\</script\>", "", boot_json)

    # TODO: Find better fix
    boot_json = re.sub(r"</script\>", "", boot_json)

    user = frappe.db.get_value("User", frappe.session.user, '*', as_dict=1)

    beneficiary_data = frappe.db.get_value('qp_PO_Beneficiario', {'email': user.email}, '*', as_dict=1)

    if not beneficiary_data:
        frappe.throw("Beneficiario aun no ha sido registrado. Por favor comunique al Administrador.", frappe.PermissionError)

    context.update({
        "is_navbar_custom": True,
        "csrf_token": csrf_token,
        "beneficiary_data":beneficiary_data,
        "no_cache":1
    })
        
    return context