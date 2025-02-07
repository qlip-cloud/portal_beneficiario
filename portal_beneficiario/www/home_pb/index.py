import frappe
import os, re
import json
from frappe import _
import frappe.sessions
from six import string_types
from frappe.utils import getdate, now


def get_context(context):
  
    if frappe.session.user == "Guest":
        frappe.throw(_("Log in to access this page."), frappe.PermissionError)

    try:
        context.no_cache = 1

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

        try:
            user = frappe.db.get_value("User", frappe.session.user, '*', as_dict=1)
        except Exception as e:
            frappe.log_error(title='Excepcion en getUser()', message=f'Error en datos del beneficiario: {frappe.session.user}{e}')
            return e

        try:
            beneficiary_data = frappe.db.get_value('qp_PO_Beneficiario', {'email': user.email}, '*', as_dict=1)
            
            if beneficiary_data is None:
                frappe.throw("Beneficiario aun no ha sido registrado. Por favor comunique al Administrador.", frappe.PermissionError)

        except Exception as e:
            frappe.log_error(title='Excepcion en beneficiary_data()', message=f'Error en datos del beneficiario: {e}')
            return e

        try:
            id_contact = frappe.db.get_value("Contact", {'user': user.email}, '*', as_dict=1)
            name_beneficiary = ""
            
            if id_contact:
                id_contact = id_contact.name.split("-")[-1]
                
                if id_contact:
                    name_beneficiary = frappe.db.get_value('Supplier', {'supplier_name': id_contact}, '*', as_dict=1)
                    name_beneficiary = name_beneficiary.first_name
        
        except Exception as e:
            frappe.log_error(title='Excepcion en id_contact()', message=f'Error en datos del beneficiario: {e}')
            return e

        context.update({
            "is_navbar_custom": True,
            "csrf_token": csrf_token,
            "beneficiary_data":beneficiary_data,
            "beneficiary_name": name_beneficiary,
            "no_cache":1
        })
            
        return context
    
    except Exception as exc:
        traceback = frappe.get_traceback()
        frappe.log_error(title='Error en context', message=traceback)
        print(traceback)
        context.has_error = True
        return exc
