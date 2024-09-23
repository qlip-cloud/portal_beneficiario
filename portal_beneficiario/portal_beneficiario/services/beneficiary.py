import frappe
import os, re
import json
from frappe import _
import frappe.sessions
from six import string_types
from frappe.utils import getdate
from . import constantes

@frappe.whitelist()
def save_beneficiary(**args):
    #Se procede a guardar el beneficiario
    b = frappe.get_doc('qp_PO_Beneficiario', args.get('name'))

    try:
        b.phone = args.get('phone')
        b.nationality = args.get('nationality').upper()
        b.address = args.get('address').upper()
        b.country = args.get('country').upper()
        b.city = args.get('city').upper()
        b.business_activity = args.get('business_type')

        print("ATTACH:----------------", args.get('fileToUpload'))

        # Economic validations
        if args.get('business_type') == constantes.CODIGO_INDEPENDIENTE:
            b.economic_activity = args.get('business') 
        elif args.get('business_type') == constantes.CODIGO_EMPLEADO:
            b.economic_activity = constantes.CODIGO_ASALARIADO
        else:
            b.economic_activity = ""

        b.peps = args.get('pep')
        # Peps validations
        if int(args.get('pep')) == 1:
            b.position = args.get('pep_position').upper() if args.get('pep_position') else ""
            b.link_date = getdate(args.get('link_date')) if args.get('link_date') else ""
            b.link_undate = getdate(args.get('link_undate')) if args.get('link_undate') else ""
        else:
            b.position = ""
            b.link_date = ""
            b.link_undate = ""
        
        b.peps_parent = args.get('fpep')
        # Peps Family
        if int(args.get('fpep')) == 1:
            b.parent_name = args.get('fpep_name').upper() if args.get('fpep_name') else ""
            b.parent_type = args.get('parent_type') if args.get('parent_type') else ""
        else:
            b.parent_name = ""
            b.parent_type = ""

        b.income =  args.get('in')
        b.egress =  args.get('out')
        b.assets = args.get('assets')
        b.passive = args.get('passive')
        b.data_declaration = args.get('term_conditions') if args.get('term_conditions') else 1
        b.authorization_declaration = args.get('term_conditions') if args.get('term_conditions') else 1
        b.email = args.get('email').upper()
        b.source_fund = args.get('source_fund').upper()
        b.account_type = args.get('type_account').upper()

    except Exception as e:
        return 
    else:
        b.save()
        frappe.db.commit()
        return b

@frappe.whitelist()
def get_status():
    user = frappe.db.get_value("User", frappe.session.user, '*', as_dict=1)
    beneficiary_status = frappe.db.get_value('qp_PO_Beneficiario', {'email': user.email}, 'jumio_status', as_dict=1)
    return beneficiary_status.jumio_status
