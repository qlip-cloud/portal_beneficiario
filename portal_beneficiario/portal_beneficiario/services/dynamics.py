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
        endpoint = endpoint.format(beneficiary_data.id_dynamics)

        headers = {
                    "Authorization": f"Bearer {api_token}",
                    "Content-Type": "application/json"
                }
        
        data_parent_name = beneficiary_data.parent_name[0:100] if beneficiary_data.peps_parent and beneficiary_data.parent_name is not None else ''
        data_position = beneficiary_data.position[0:100] if beneficiary_data.peps_parent and beneficiary_data.parent_name is not None else ''
        data_date = beneficiary_data.link_date.strftime("%Y-%m-%d %H:%M:%S") if beneficiary_data.link_date is not None else ''    
        data_undate = beneficiary_data.link_undate.strftime("%Y-%m-%d %H:%M:%S") if beneficiary_data.link_undate is not None else ''
        data_birthday = beneficiary_data.birthday.strftime("%Y-%m-%d %H:%M:%S") if beneficiary_data.birthday is not None else ''
        data_document_expedition_date = beneficiary_data.document_expedition_date.strftime("%Y-%m-%d %H:%M:%S") if beneficiary_data.document_expedition_date is not None else ''

        data = {
            "name": f'{beneficiary_data.be_name} {beneficiary_data.surname}',
            "bit_genero": gender_switch(beneficiary_data.gender),
            "bit_fecha_nacimiento": data_birthday,
            "bit_fecha_expedicion_documento": data_document_expedition_date,
            "bit_nacionalidad": beneficiary_data.nationality,
            "telephone1": beneficiary_data.phone,
            "bit_persona_politicamente_expuesta": isBoolean(beneficiary_data.peps),
            "bit_parentescoconpep": isBoolean(beneficiary_data.peps_parent),
            "bit_nombredelpeprelacionado": data_parent_name, 
            "bit_cargo": data_position,
            "bit_fechavinculacionalargo": data_date,
            "address1_line1": beneficiary_data.address,
            "bit_salario": beneficiary_data.income,
            "revenue":beneficiary_data.assets,
            "bit_otros_rendimientos":beneficiary_data.egress,
            "bit_pasivo": beneficiary_data.passive,
            "bit_patrimonio_nuevo":beneficiary_data.patrimony,
            "bit_origendelosrecursosarecibir": beneficiary_data.source_fund, 
            "bit_score_jumio": int(beneficiary_data.jumio_points),
            "bit_nada": beneficiary_data.business_activity
        }

        # Data Empty
        if data_undate:
            data["bit_fechadesvinculacionalcargo"] = data_undate
 
        if beneficiary_data.economic_activity:
            economic_data = frappe.db.get_value('qp_PO_EconomicActivity', {'ea_code': beneficiary_data.economic_activity}, '*', as_dict=1)
            data_guid = economic_data.ea_guid
            data["bit_ClaseActividadEconomica@odata.bind"] = f'/bit_claseeconmicas({data_guid})'

        # Parse data
        all_data = json.dumps(data)

        response=None
        try:
            response = requests.request("PATCH", endpoint, data=all_data, headers=headers)
            if response:
                saveDynamicsResponse(beneficiary_data, all_data, response) 
                return 1
        except Exception as e:

            raise e 
        else:
            saveDynamicsResponse(beneficiary_data, all_data, response)
            return response
        
def gender_switch(gender):
    if gender == "M":
        return 913610000
    elif gender == "F":
        return 913610001
    else:
        return 913610002
    
def isBoolean(field):
    if field == 0:
        return False
    else:
        return True
    
def saveDynamicsResponse(beneficiary, request, response):

    if frappe.db.exists("qp_PO_DynamicsAttemps", {"parent": beneficiary.name}):
        dynamics_attemps = frappe.db.get_value("qp_PO_DynamicsAttemps", {"parent": beneficiary.name}, '*', as_dict=1)
        frappe.db.set_value('qp_PO_DynamicsAttemps', dynamics_attemps.name, "attemps_num", dynamics_attemps.attemps_num + 1)
        frappe.db.set_value('qp_PO_DynamicsAttemps', dynamics_attemps.name, "send_status", response.status_code)
        frappe.db.set_value('qp_PO_DynamicsAttemps', dynamics_attemps.name, "query", request)
        frappe.db.set_value('qp_PO_DynamicsAttemps', dynamics_attemps.name, "response", response.content)
    else:
        ja = frappe.get_doc({
            "doctype":"qp_PO_DynamicsAttemps", 
            "parent": beneficiary.name, 
            "parentfield":"dynamics_attemps",
            "parenttype":"qp_PO_Beneficiario", 
            "attemps_num":1,
            "send_status": response.status_code,
            "query": request,
            "response":response.content
        })

        ja.insert()

    frappe.db.commit()