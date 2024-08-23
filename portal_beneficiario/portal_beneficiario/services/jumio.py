import frappe
import os, re
import json
from frappe import _
import frappe.sessions
from six import string_types
from frappe.utils import getdate
from frappe.integrations.utils import make_get_request, make_post_request


def get_jumio_accesstoken(jumio_cnf):

    if jumio_cnf:
        endpoint = jumio_cnf.access_token_url
        headers = {"Authorization": f"token {jumio_cnf.client_id}:{jumio_cnf.client_secret}"}
        data = {"grant_type": "client_credentials"}

        response=None
        try:
            response = frappe._dict(make_get_request(endpoint, data=data, headers=headers))
        except Exception as e:
             print(e)
             return
        else:
            return response.access_token

@frappe.whitelist()
def get_jumio_iframe():
    
    jumio_cnf = frappe.db.get_list("qp_PO_JumioConfig", fields=["*"])[0]

    user = frappe.db.get_value("User", frappe.session.user, '*', as_dict=1)

    beneficiary_data = frappe.db.get_value('qp_PO_Beneficiario', {'email': user.email}, '*', as_dict=1)

    if jumio_cnf and beneficiary_data:

        api_token = get_jumio_accesstoken(jumio_cnf)
        endpoint = jumio_cnf.jumio_service_url
        headers = {"Authorization": f"Bearer {api_token}"}

        data = {
            "customerInternalReference":beneficiary_data.id_dynamics,
            "workflowDefinition":{
                "key": beneficiary_data.id_jumio
            }
        }

        response=None

        try:
            response = frappe._dict(make_post_request(endpoint, data=data, headers=headers))

            print(frappe._dict(response.workflowExecution).id)
            print(frappe._dict(response.account).id)

            if response:
                frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "jumio_workflowExecution", frappe._dict(response.workflowExecution).id)
                frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "jumio_account", frappe._dict(response.account).id)
                frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "jumio_iframe", frappe._dict(response.web).href)
                frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "enable", 0)
                frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "jumio_status", "PENDING")
                frappe.db.commit()
        except Exception as e:
            print(e) 
            return
        else:
            return response


@frappe.whitelist(allow_guest=True)
def callback(**args):
	#pack your parameters back into a dictionary
    args=frappe._dict(args)
    beneficiary_data = frappe.db.get_value('qp_PO_Beneficiario', {'jumio_workflowExecution': frappe._dict(args.workflowExecution).id, "jumio_account":frappe._dict(args.account).id}, '*', as_dict=1)
    
    if beneficiary_data:
        frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "jumio_status", frappe._dict(args.workflowExecution).status)
        frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "enable", 1)
        frappe.db.commit()
        return 0
    else:
        return 1
