import frappe
import os, re
import json,datetime
import frappe.sessions
import requests
import base64
from frappe import _
from six import string_types
from frappe.utils import getdate
from frappe.integrations.utils import make_get_request, make_post_request
from six import string_types, text_type
from urllib.parse import quote_plus


def get_dynamic_accesstoken(dynamic_cnf):

    if dynamic_cnf:
        endpoint = str(dynamic_cnf.access_token_url)
   
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        data = f'grant_type=client_credentials&client_id={dynamic_cnf.client_id}&client_secret={dynamic_cnf.client_secret}&resource={quote_plus(dynamic_cnf.dynamic_resource_url)}'

        response=None
        try:
            response = make_post_request(endpoint, data=data, headers=headers)
        except Exception as e:
             raise e 
        else:
            return response.get("access_token")
        
@frappe.whitelist()
def call_dynamic():
    
    dynamic_cnf = frappe.db.get_list("qp_PO_DynamicConfigs", fields=["*"])[0]

    user = frappe.db.get_value("User", frappe.session.user, '*', as_dict=1)

    beneficiary_data = frappe.db.get_value('qp_PO_Beneficiario', {'email': user.email}, '*', as_dict=1)

    if dynamic_cnf and beneficiary_data:

        api_token = get_dynamic_accesstoken(dynamic_cnf)
        endpoint = dynamic_cnf.dynamic_url
        endpoint = endpoint.format(beneficiary_data.jumio_account)
        #headers = {"Authorization": f"Bearer {api_token}"}

        headers = {
                    "Authorization": f"Bearer {api_token}",
                    "Content-Type": "application/json"
                }
        
        data_parent_name = beneficiary_data.parent_name[0:100] if beneficiary_data.peps_parent and beneficiary_data.parent_name is not None else ''
        data_position = beneficiary_data.position[0:100] if beneficiary_data.peps_parent and beneficiary_data.parent_name is not None else ''
        data_date = beneficiary_data.link_date.strftime("%Y-%m-%d %H:%M:%S") if beneficiary_data.link_date is not None else ''    
        data_undate = beneficiary_data.link_undate.strftime("%Y-%m-%d %H:%M:%S") if beneficiary_data.link_undate is not None else ''

        data = {
            "bit_persona_politicamente_expuesta": beneficiary_data.peps,
            "bit_parentescoconpep": beneficiary_data.peps_parent,
            "bit_nombredelpeprelacionado": data_parent_name, 
            "bit_cargo": data_position,
            "bit_fechavinculacionalargo": data_date,
            "bit_fechadesvinculacionalcargo": data_undate,
            "address1_line1": beneficiary_data.address,
            "bit_salario": beneficiary_data.income,
            "revenue":float(0),
            "bit_pasivo": beneficiary_data.egress,
            "bit_patrimonio_nuevo":beneficiary_data.patrimony,
            "bit_origendelosrecursosarecibir": beneficiary_data.source_fund, 
            "bit_score_jumio": int(beneficiary_data.jumio_points)
        }

        response=None

        try:
            #response = make_post_request(endpoint, data=data, headers=headers)
            response = requests.put(endpoint, data=data, headers=headers)

            if response:
                return 1
        except Exception as e:
            raise e 
        else:
            return response