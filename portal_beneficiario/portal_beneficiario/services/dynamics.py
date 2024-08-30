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

def get_dynamic_accesstoken(dynamic_cnf):

    if dynamic_cnf:
        endpoint = dynamic_cnf.access_token_url
        #print(credentials)

        headers = {"Content-Type":"application/x-www-form-urlencoded"}
        data = f'grant_type=client_credentials&client_id={dynamic_cnf.client_id}&client_secret={dynamic_cnf.client_secret}&resource=https://stonexpruebas.crm.dynamics.com/'

        response=None
        try:
            response = make_get_request(endpoint, data=data, headers=headers)
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
        headers = {"Authorization": f"Bearer {api_token}"}
        data = {
            "bit_persona_politicamente_expuesta": False,
            "bit_parentescoconpep": True,
            "bit_nombredelpeprelacionado":"Jhonnie Walker", 
            "bit_cargo":"Chairman", 
            "bit_fechavinculacionalargo": "2024-12-31 00:00:00",
            "bit_fechadesvinculacionalcargo":"2025-12-31 00:00:00",
            "address1_line1": "Cl 1",
            "bit_salario": 3500,
            "bit_otros_rendimientos":100,
            "revenue":100,
            "bit_pasivo":500,
            "bit_patrimonio_nuevo":1000,
            "bit_origendelosrecursosarecibir": 913610000, 
            "bit_score_jumio": 50
        }

        response=None

        try:
            response = make_post_request(endpoint, data=data, headers=headers)

            if response:
                return 1
        except Exception as e:
            raise e 
        else:
            return response