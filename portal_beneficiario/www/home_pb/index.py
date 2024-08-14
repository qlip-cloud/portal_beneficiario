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
    elif frappe.db.get_value("User", frappe.session.user, "user_type") == "Website User":
        frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

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
        "beneficiary_data":beneficiary_data
    })
        
    return context

@frappe.whitelist()
def save_beneficiary(**args):

    b = frappe.get_doc('qp_PO_Beneficiario', args.get('name'))
    b.phone = args.get('phone')
    b.nationality = args.get('nationality')
    b.address = args.get('address')
    b.city = args.get('city')
    b.economic_activity = args.get('business')
    b.peps = args.get('pep')
    b.position = args.get('position')
    b.link_date = getdate(args.get('link_date'))
    b.business_activity = args.get('business_type')
    b.peps_parent = args.get('fpep')
    b.parent_name = args.get('fpep_name')
    b.parent_type = args.get('parent_type')
    b.income =  args.get('in')
    b.egress =  args.get('out')
    b.assets = args.get('assets')
    b.passive = args.get('passive')
    b.data_declaration = args.get('term_conditions') if args.get('term_conditions') else 1
    b.authorization_declaration = args.get('term_conditions') if args.get('term_conditions') else 1
    b.email = args.get('email')
    b.source_fund = args.get('source_fund')

    b.save()

    frappe.db.commit()

    return b
