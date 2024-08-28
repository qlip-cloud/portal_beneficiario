import frappe
import os, re
import json,datetime
from frappe import _
import frappe.sessions
from six import string_types
from frappe.utils import getdate
from frappe.integrations.utils import make_get_request, make_post_request
import base64
from six import string_types, text_type


def get_jumio_accesstoken(jumio_cnf):

    if jumio_cnf:
        endpoint = jumio_cnf.access_token_url
        credentials = base64.b64encode(f"{jumio_cnf.client_id}:{jumio_cnf.client_secret}".encode()).decode("utf-8")

        #print(credentials)

        headers = { 
            "Authorization": f"Basic {credentials}",
            "Content-Type":"application/x-www-form-urlencoded"}
        data = 'grant_type=client_credentials'

        response=None
        try:
            response = make_post_request(endpoint, data=data, headers=headers)
        except Exception as e:
             raise e 
        else:
            return response.get("access_token")

@frappe.whitelist()
def get_jumio_iframe():
    
    jumio_cnf = frappe.db.get_list("qp_PO_JumioConfig", fields=["*"])[0]

    user = frappe.db.get_value("User", frappe.session.user, '*', as_dict=1)

    beneficiary_data = frappe.db.get_value('qp_PO_Beneficiario', {'email': user.email}, '*', as_dict=1)
    
    if jumio_cnf and beneficiary_data:

        if beneficiary_data.jumio_status != "PROCESSED":
            api_token = get_jumio_accesstoken(jumio_cnf)
            endpoint = jumio_cnf.account_url
            headers = {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json"
                }

            data = json.dumps({
                "customerInternalReference":beneficiary_data.id_dynamics,
                "workflowDefinition":{
                    "key": jumio_cnf.id_jumio
                }
            })

            response=None

            try:
                response = make_post_request(endpoint, data=data, headers=headers)

                #print(frappe._dict(response.workflowExecution).id)
                #print(frappe._dict(response.account).id)

                if response:
                    frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "jumio_workflowExecution", response.get("workflowExecution").get("id"))
                    frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "jumio_account", response.get("account").get("id"))
                    frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "jumio_iframe", response.get("web").get("href"))
                    frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "enable", 0)
                    frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "jumio_status", "PENDING")
                    frappe.db.commit()
            except Exception as e:
                raise e 
            else:
                return response
        else:
            return {"web":{"href":beneficiary_data.jumio_iframe}}
        
@frappe.whitelist()
def get_jumio_retrieval():
    
    jumio_cnf = frappe.db.get_list("qp_PO_JumioConfig", fields=["*"])[0]

    user = frappe.db.get_value("User", frappe.session.user, '*', as_dict=1)

    beneficiary_data = frappe.db.get_value('qp_PO_Beneficiario', {'email': user.email}, '*', as_dict=1)

    if jumio_cnf and beneficiary_data:

        api_token = get_jumio_accesstoken(jumio_cnf)
        endpoint = jumio_cnf.retrieval_url
        endpoint = endpoint.format(beneficiary_data.jumio_account, beneficiary_data.jumio_workflowexecution)
        headers = {"Authorization": f"Bearer {api_token}"}
        data = {}

        
        response=None

        try:
            response = make_get_request(endpoint, data=data, headers=headers)

            if response:

                frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "jumio_points", response.get("decision").get("risk").get("score"))

                if frappe.db.exists("qp_PO_JumioAttemps", {"parent": beneficiary_data.name}):
                    jumio_attemps = frappe.db.get_value("qp_PO_JumioAttemps", {"parent": beneficiary_data.name}, '*', as_dict=1)
                    frappe.db.set_value('qp_PO_JumioAttemps', jumio_attemps.name, "attemps_num", jumio_attemps.attemps_num + 1)
                    frappe.db.set_value('qp_PO_JumioAttemps', jumio_attemps.name, "query", json.dumps(data, default=json_handler))
                    frappe.db.set_value('qp_PO_JumioAttemps', jumio_attemps.name, "response", json.dumps(response, default=json_handler))
                else:
                    ja = frappe.get_doc({
                        "doctype":"qp_PO_JumioAttemps", 
                        "parent": beneficiary_data.name, 
                        "parentfield":"jumio_attemps",
                        "parenttype":"qp_PO_Beneficiario", 
                        "attemps_num":0,
                        "query":json.dumps(data, default=json_handler),
                        "response":json.dumps(response, default=json_handler)
                    })

                    ja.insert()

                frappe.db.commit()
        except Exception as e:
            raise e 
        else:
            return response


@frappe.whitelist(allow_guest=True)
def callback(**args):
	#pack your parameters back into a dictionary

    beneficiary_data = frappe.db.get_value('qp_PO_Beneficiario', {'jumio_workflowExecution': args.get("workflowExecution").get("id"), "jumio_account":args.get("account").get("id")}, '*', as_dict=1)
    
    if beneficiary_data:
        frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "jumio_status", args.get("workflowExecution").get("status"))
        frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "enable", 1)
        frappe.db.commit()
        return 0
    else:
        return 1
    
def json_handler(obj):
	if isinstance(obj, (datetime.date, datetime.timedelta, datetime.datetime)):
		return text_type(obj)
