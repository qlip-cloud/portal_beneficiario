import frappe
import os, re
import json
from frappe import _
import frappe.sessions
from six import string_types
from frappe.utils import getdate

@frappe.whitelist()
def save_beneficiary(**args):
    #Se procede a guardar el beneficiario
    b = frappe.get_doc('qp_PO_Beneficiario', args.get('name'))

    try:
        b.phone = args.get('phone')
        b.nationality = args.get('nationality')
        b.address = args.get('address')
        b.city = args.get('city')
        b.peps = args.get('pep')
        b.position = args.get('pep_position')
        b.link_date = getdate(args.get('link_date'))
        b.link_undate = getdate(args.get('link_undate'))
        b.business_activity = args.get('business_type')
        b.economic_activity = args.get('business')
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
        b.account_type = args.get('type_account')

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
