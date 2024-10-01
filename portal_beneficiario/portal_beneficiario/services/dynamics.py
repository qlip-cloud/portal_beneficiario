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
from datetime import datetime
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
        
        if beneficiary_data.document_type:
            document_type = frappe.db.get_value('qp_PO_DocumentType', {'do_name': beneficiary_data.document_type}, '*', as_dict=1)
            data_document_type = document_type.do_code

        if beneficiary_data.country_of_birth:
            get_country = frappe.db.get_value('qp_PO_Country', {'co_code': beneficiary_data.country_of_birth}, '*', as_dict=1)
            data_place_birth = get_country.co_guid_code
        
        if beneficiary_data.city_of_birth:
            get_city = frappe.db.get_value('qp_PO_City', {'ci_code': beneficiary_data.city_of_birth}, '*', as_dict=1)
            data_city_birth = get_city.ci_guid_code

        if beneficiary_data.business_activity:
            get_bussines_sector = frappe.db.get_value('qp_PO_BusinessActivity', {'ba_code': beneficiary_data.business_activity}, '*', as_dict=1)
            data_business = get_bussines_sector.ba_code
            data_industrial_sector = get_bussines_sector.ba_industrial_sector

        data_parent_name = beneficiary_data.parent_name[0:100] if beneficiary_data.peps_parent and beneficiary_data.parent_name is not None else ''
        data_position = beneficiary_data.position[0:100]
        data_date = beneficiary_data.link_date.strftime("%Y-%m-%d %H:%M:%S") if beneficiary_data.link_date is not None else ''    
        data_undate = beneficiary_data.link_undate.strftime("%Y-%m-%d %H:%M:%S") if beneficiary_data.link_undate is not None else ''
        data_birthday = beneficiary_data.birthday.strftime("%Y-%m-%d %H:%M:%S") if beneficiary_data.birthday is not None else ''
        data_document_expedition_date = beneficiary_data.document_expedition_date.strftime("%Y-%m-%d %H:%M:%S") if beneficiary_data.document_expedition_date is not None else ''
        data_date_now = datetime.now()

        data = {
            "bit_genero": gender_switch(beneficiary_data.gender),
            "bit_fecha_nacimiento": data_birthday,
            "bit_fecha_expedicion_documento": data_document_expedition_date,
            "bit_tipo_de_documento": data_document_type,
            "bit_numero_documento_jumio": beneficiary_data.document_number,
            "bit_lugarexpedicion": beneficiary_data.document_expedition_country,
            "bit_lugar_de_nacimiento_jumio": beneficiary_data.document_expedition_city,
            "bit_Pais_Nacimiento@odata.bind":  f'/bit_pases({data_place_birth})',
            "bit_Lugar_Nacimiento@odata.bind": f'/bit_ciudads({data_city_birth})',
            "bit_nacionalidad": beneficiary_data.nationality.upper(),
            "telephone3": beneficiary_data.phone,
            "bit_persona_politicamente_expuesta": isBoolean(beneficiary_data.peps),
            "bit_parentescoconpep": isBoolean(beneficiary_data.peps_parent),
            "address1_line1": beneficiary_data.address,
            "bit_salario": beneficiary_data.income,
            "revenue":beneficiary_data.assets,
            "bit_otros_rendimientos":beneficiary_data.egress,
            "bit_pasivo": beneficiary_data.passive,
            "bit_patrimonio_nuevo":beneficiary_data.patrimony,
            "bit_origendelosrecursosarecibir": beneficiary_data.source_fund, 
            "bit_score_jumio": int(beneficiary_data.jumio_points),
            "bit_notas_jumio": beneficiary_data.jumio_rejects,
            "bit_nada": data_business,
            "bit_sectorindustrial": data_industrial_sector,
            "bit_fechacorteinformacionfinanciera": data_date_now.strftime("%Y-%m-%d %H:%M:%S"),
            "bit_canal": 913610001
        }

        # Data Empty
        if data_position:
            data["bit_cargo"] = ''.join(data_position)

        if data_date:
            data["bit_fechavinculacionalargo"] = data_date

        if data_undate:
            data["bit_fechadesvinculacionalcargo"] = data_undate

        if data_parent_name:
            data["bit_nombredelpeprelacionado"] = data_parent_name

        # Send Attach
        # sendDocumentDynamics(beneficiary_data, dynamic_cnf, api_token)   
 
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
                saveRequestResponseDynamics(beneficiary_data, all_data, response, "send_status", "query", "response", doc_attemps=True)
                get_bank_account(beneficiary_data, dynamic_cnf, api_token, beneficiary_data.id_dynamics, beneficiary_data.account_number[-4:])
                return 1
        except Exception as e:

            raise e 
        else:
            saveRequestResponseDynamics(beneficiary_data, all_data, response, "send_status", "query", "response", doc_attemps=True)
            return response


def get_bank_account(beneficiary, dynamics_conf, token, id_dynamics, account_last_numbers):

    headers = {
            "Authorization": f"Bearer {token}"
    }
  
    endpoint = dynamics_conf.dynamic_account_url
    endpoint = endpoint.format(id_dynamics, account_last_numbers)

    response=None
    try:
        response = requests.get(endpoint, headers=headers)
        if response:
            data = response.json()

            # Data
            if len(data.get('value')) > 0:
                saveRequestResponseDynamics(beneficiary, endpoint, response, "send_status_account_bank", "query_account_bank", "response_account_bank", doc_attemps=False)

                # Send code type account
                id_bancario = data.get('value')[0].get('bit_datos_bancariosid')
                update_banking_dato(beneficiary, dynamics_conf, token, id_bancario)
            else:
                saveRequestResponseDynamics(beneficiary, endpoint, response, "send_status_account_bank", "query_account_bank", "response_account_bank", doc_attemps=False)   

            return 1
    except Exception as e:
        raise e 
    else:
        saveRequestResponseDynamics(beneficiary, endpoint, response, "send_status_account_bank", "query_account_bank", "response_account_bank", doc_attemps=False)
        return response


def update_banking_dato(beneficiary, dynamics_conf, token, id_account):
    endpoint = dynamics_conf.dynamic_update_account_url
    endpoint = endpoint.format(id_account)

    headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
    }

    data = {
            "bit_tipo_producto": beneficiary.account_type,
            "statuscode": 1,
    }

    # Parse data
    parse_data = json.dumps(data)

    response=None
    try:
        response = requests.request("PATCH", endpoint, data=parse_data, headers=headers)
        if response:
            saveRequestResponseDynamics(beneficiary, parse_data, response, "send_status_dato", "query_dato", "response_dato", doc_attemps=False)
            return 1
    except Exception as e:
        raise e 
    else:
        saveRequestResponseDynamics(beneficiary, parse_data, response, "send_status_dato", "query_dato", "response_dato", doc_attemps=False)
        return response


def sendDocumentDynamics(beneficiary, dynamics_conf, token):

    # docAttach = frappe.db.get_value("File", {"attached_to_name": beneficiary.name})
    doc_attach = frappe.db.get_value('File', {'attached_to_name': beneficiary.name}, '*', as_dict=1)
    doc_extension = extFile(doc_attach.file_name.split(".")[-1])
    
    doc_name =  frappe.db.get("File", {"attached_to_name": beneficiary.name}).name
    doc_content = base64.b64encode(frappe.get_doc("File", doc_name).get_content())

    endpoint = dynamics_conf.dynamic_document_url

    headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
    
    data = {
        "subject": "Documento Stonex",
        "filename": doc_attach.file_name,
        "documentbody": doc_content.decode("utf-8"),
        "mimetype": doc_extension,
        "objectid_account@odata.bind": f'/accounts({beneficiary.id_dynamics})'
    }
        
    # Parse data
    all_data = json.dumps(data)

    response=None
    try:
        response = requests.request("POST", endpoint, data=all_data, headers=headers)
        if response:
            saveRequestResponseDynamics(beneficiary, all_data, response, "send_status_attach", "query_attach", "response_attach")
            pass
            return 1
    except Exception as e:

        raise e 
    else:
        saveRequestResponseDynamics(beneficiary, all_data, response, "send_status_attach", "query_attach", "response_attach")
        return response
    

def saveRequestResponseDynamics(beneficiary, request, response, doc_status_code, doc_request, doc_response, doc_attemps=False):
    if frappe.db.exists("qp_PO_DynamicsAttemps", {"parent": beneficiary.name}):
        dynamics_attemps = frappe.db.get_value("qp_PO_DynamicsAttemps", {"parent": beneficiary.name}, '*', as_dict=1)

        if doc_attemps:
            frappe.db.set_value('qp_PO_DynamicsAttemps', dynamics_attemps.name, "attemps_num", dynamics_attemps.attemps_num + 1)

        frappe.db.set_value('qp_PO_DynamicsAttemps', dynamics_attemps.name, doc_status_code, response.status_code)
        frappe.db.set_value('qp_PO_DynamicsAttemps', dynamics_attemps.name, doc_request, request)
        frappe.db.set_value('qp_PO_DynamicsAttemps', dynamics_attemps.name, doc_response, response.content)
    else:
        ja = frappe.get_doc({
            "doctype":"qp_PO_DynamicsAttemps", 
            "parent": beneficiary.name, 
            "parentfield":"dynamics_attemps",
            "parenttype":"qp_PO_Beneficiario",
            "attemps_num": 1,
            doc_status_code: response.status_code,
            doc_request: request,
            doc_response: response.content
        })

        ja.insert()

    frappe.db.commit()


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
    
def extFile(extension):
    if extension == "png":
        return "image/png"
    elif extension == "jpeg" or extension == "jpg":
        return "image/jpeg"
    elif extension == "pdf":
        return "application/pdf"