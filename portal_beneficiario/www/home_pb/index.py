import frappe
import os, re
import json
from frappe import _
import frappe.sessions
from six import string_types
from frappe.utils import getdate, now
import traceback

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Beneficiario aún no ha sido registrado. Por favor comunique al Administrador."), frappe.PermissionError)

    context.no_cache = 1

    try:
        try:
            boot = frappe.sessions.get()
        except Exception as e:
            boot = frappe._dict(status='failed', error=str(e))
            frappe.log_error(title='Excepción en get_context (boot)', message=f'Error al obtener boot de sesión: {e}\n{frappe.get_traceback()}')

        csrf_token = frappe.sessions.get_csrf_token()
        frappe.db.commit()

        boot_json = frappe.as_json(boot)
        boot_json = re.sub(r"\<script[^<]*\</script\>", "", boot_json)
        boot_json = re.sub(r"</script\>", "", boot_json)

        user = None
        try:
            user = frappe.db.get_value("User", frappe.session.user, '*', as_dict=1)
            if not user:
                frappe.throw(_("Usuario no encontrado. Por favor comunique al Administrador."), frappe.PermissionError)
        except Exception as e:
            frappe.log_error(title='Excepción en get_context (getUser)', message=f'Error al obtener datos del usuario {frappe.session.user}: {e}\n{frappe.get_traceback()}')
            frappe.throw(_("Error al cargar datos de usuario. Por favor intente de nuevo o comunique al Administrador."), frappe.ValidationError)

        beneficiary_data = None
        try:
            if user and user.email:
                beneficiary_data = frappe.db.get_value('qp_PO_Beneficiario', {'email': user.email}, '*', as_dict=1)

            if beneficiary_data is None:
                frappe.throw(_("Beneficiario aún no ha sido registrado. Por favor comunique al Administrador."), frappe.PermissionError)

        except frappe.DoesNotExistError:
            frappe.log_error(title='Excepción en get_context (beneficiary_data)', message=f'Beneficiario no encontrado para el email {user.email if user else "N/A"}.\n{frappe.get_traceback()}')
            frappe.throw(_("Beneficiario aún no ha sido registrado. Por favor comunique al Administrador."), frappe.PermissionError)
        except Exception as e:
            frappe.log_error(title='Excepción en get_context (beneficiary_data)', message=f'Error al obtener datos del beneficiario para el email {user.email if user else "N/A"}: {e}\n{frappe.get_traceback()}')
            frappe.throw(_("Error al cargar datos del beneficiario. Por favor intente de nuevo o comunique al Administrador."), frappe.ValidationError)

        name_beneficiary = ""
        try:
            if user and user.email:
                id_contact = frappe.db.get_value("Contact", {'user': user.email}, '*', as_dict=1)

                if id_contact:
                    contact_name_parts = id_contact.name.split("-")
                    if contact_name_parts:
                        contact_id = contact_name_parts[-1]
                        if contact_id:
                            supplier_data = frappe.db.get_value('Supplier', {'supplier_name': contact_id}, '*', as_dict=1)
                            if supplier_data and supplier_data.first_name:
                                name_beneficiary = supplier_data.first_name
        except Exception as e:
            frappe.log_error(title='Excepción en get_context (id_contact/name_beneficiary)', message=f'Error al obtener nombre del beneficiario desde Contact/Supplier: {e}\n{frappe.get_traceback()}')

        context.update({
            "is_navbar_custom": True,
            "csrf_token": csrf_token,
            "beneficiary_data": beneficiary_data,
            "beneficiary_name": name_beneficiary,
            "no_cache": 1
        })

        return context

    except frappe.ValidationError as ve:
        frappe.log_error(title='Error de Validación en get_context', message=f'Error de validación: {ve}\n{frappe.get_traceback()}')
        pass

    except frappe.PermissionError as pe:
        frappe.log_error(title='Error de Permiso en get_context', message=f'Error de permiso: {pe}\n{frappe.get_traceback()}')
        pass

    except Exception as exc:
        traceback_str = traceback.format_exc()
        frappe.log_error(title='Error general en get_context', message=f'Error inesperado: {exc}\n{traceback_str}')
        frappe.throw(_("Ha ocurrido un error inesperado al cargar la página. Por favor, intente de nuevo o comunique al Administrador."), frappe.ValidationError)
