import frappe
import os, re
import json, datetime
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


DYNAMICS_ERROR_PREFIX = "[Dynamics Error]"
SENSITIVE_KEYS = {
    "client_id",
    "client_secret",
    "access_token",
    "authorization",
    "password",
    "secret",
    "token",
}


def sanitize_sensitive_data(data, secrets=None):
    """Oculta credenciales (client_id, client_secret, tokens) antes de guardar en Error Log."""
    if data is None:
        return None

    secret_values = [str(s) for s in (secrets or []) if s]

    if isinstance(data, dict):
        clean = {}
        for key, value in data.items():
            key_lower = str(key).lower()
            if key_lower in SENSITIVE_KEYS:
                clean[key] = "***REDACTED***"
            elif key_lower == "documentbody" and isinstance(value, str):
                clean[key] = f"[BASE64 OMITIDO - {len(value)} chars]"
            else:
                clean[key] = sanitize_sensitive_data(value, secrets=secret_values)
        return clean

    if isinstance(data, list):
        return [sanitize_sensitive_data(item, secrets=secret_values) for item in data]

    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="replace")

    if isinstance(data, str):
        # Si es JSON válido, sanitizar sus llaves y formatear legible
        stripped = data.strip()
        if (stripped.startswith("{") and stripped.endswith("}")) or (stripped.startswith("[") and stripped.endswith("]")):
            try:
                parsed = json.loads(data)
                return json.dumps(
                    sanitize_sensitive_data(parsed, secrets=secret_values),
                    ensure_ascii=False,
                    indent=2,
                )
            except Exception:
                pass

        # Sanitizar parámetros form-urlencoded / query strings y tokens Bearer
        sanitized = re.sub(
            r'(?i)(client_id|client_secret|access_token|password|secret)=([^&\s"\']+)',
            r'\1=***REDACTED***',
            data,
        )
        sanitized = re.sub(
            r'(?i)(Bearer\s+)([^\s"\']+)',
            r'\1***REDACTED***',
            sanitized,
        )
        # Ocultar valores literales de credenciales si Dynamics/Azure AD los devuelve en el mensaje
        for secret_val in secret_values:
            sanitized = sanitized.replace(secret_val, "***REDACTED***")
        return sanitized

    return data


def parse_dynamics_error(response):
    """Extrae código y mensaje de error de respuestas de Azure AD (OAuth) o Dynamics CRM (OData)."""
    if response is None:
        return None

    payload = None
    if isinstance(response, dict):
        payload = response
    else:
        raw_body = getattr(response, "text", None)
        if raw_body is None and hasattr(response, "content"):
            raw_body = response.content
        if isinstance(raw_body, bytes):
            raw_body = raw_body.decode("utf-8", errors="replace")
        if isinstance(raw_body, str) and raw_body.strip():
            try:
                payload = json.loads(raw_body)
            except Exception:
                return None

    if not isinstance(payload, dict):
        return None

    # Formato 1: Error OAuth / Azure AD (ej. get_dynamic_accesstoken)
    if isinstance(payload.get("error"), str):
        error_code = payload.get("error")
        error_codes = payload.get("error_codes")
        if isinstance(error_codes, list) and error_codes:
            codes_str = ", ".join(str(c) for c in error_codes)
            error_code = f"{error_code} ({codes_str})"

        return {
            "code": error_code,
            "message": payload.get("error_description") or payload.get("message") or "",
            "trace_id": payload.get("trace_id"),
            "correlation_id": payload.get("correlation_id"),
        }

    # Formato 2: Error Dynamics 365 Web API / OData (ej. {"error": {"code": "...", "message": "..."}})
    if isinstance(payload.get("error"), dict):
        err_obj = payload.get("error")
        return {
            "code": err_obj.get("code") or "",
            "message": err_obj.get("message") or "",
            "trace_id": None,
            "correlation_id": None,
        }

    return None


def log_dynamics_error(
    method_name,
    endpoint=None,
    http_method=None,
    request_data=None,
    response=None,
    exception=None,
    extra_info=None,
    secrets=None,
):
    """Registra errores de integración con Dynamics con título filtrable, código/mensaje y datos sanitizados."""
    # Si make_post_request lanzó HTTPError, recuperar el response embebido en la excepción
    if response is None and exception is not None and getattr(exception, "response", None) is not None:
        response = exception.response

    parsed_error = parse_dynamics_error(response)

    title = f"{DYNAMICS_ERROR_PREFIX} {method_name}"
    if parsed_error and parsed_error.get("code"):
        title = f"{title} - {parsed_error['code']}"
    title = title[:140]

    parts = [f"Usuario: {frappe.session.user}"]

    if extra_info:
        parts.append(f"Detalle: {sanitize_sensitive_data(str(extra_info), secrets=secrets)}")

    if parsed_error:
        if parsed_error.get("code"):
            parts.append(f"Dynamics Code: {sanitize_sensitive_data(str(parsed_error['code']), secrets=secrets)}")
        if parsed_error.get("message"):
            parts.append(f"Dynamics Message: {sanitize_sensitive_data(str(parsed_error['message']), secrets=secrets)}")
        if parsed_error.get("trace_id"):
            parts.append(f"Trace ID: {parsed_error['trace_id']}")
        if parsed_error.get("correlation_id"):
            parts.append(f"Correlation ID: {parsed_error['correlation_id']}")

    if endpoint:
        method_label = f"{http_method} " if http_method else ""
        parts.append(f"Endpoint: {method_label}{sanitize_sensitive_data(str(endpoint), secrets=secrets)}")

    if request_data is not None:
        clean_req = sanitize_sensitive_data(request_data, secrets=secrets)
        if isinstance(clean_req, (dict, list)):
            clean_req = json.dumps(clean_req, ensure_ascii=False, indent=2)
        parts.append(f"Request:\n{clean_req}")

    if response is not None:
        if hasattr(response, "status_code"):
            parts.append(f"Response Status: {response.status_code}")
            body = getattr(response, "text", None)
            if body is None and hasattr(response, "content"):
                body = response.content
            parts.append(f"Response Body:\n{sanitize_sensitive_data(body, secrets=secrets)}")
        else:
            clean_resp = sanitize_sensitive_data(response, secrets=secrets)
            if isinstance(clean_resp, (dict, list)):
                clean_resp = json.dumps(clean_resp, ensure_ascii=False, indent=2)
            parts.append(f"Response:\n{clean_resp}")

    if exception is not None:
        parts.append(f"Exception: {sanitize_sensitive_data(str(exception), secrets=secrets)}")
        tb = frappe.get_traceback()
        if tb and "NoneType: None" not in tb:
            parts.append(f"Traceback:\n{sanitize_sensitive_data(tb, secrets=secrets)}")

    frappe.log_error(title=title, message="\n\n".join(parts))
    return parsed_error


def get_dynamic_config():
    configs = frappe.db.get_all("qp_PO_DynamicConfigs", fields=["name"])
    if not configs:
        return None

    doc = frappe.get_doc("qp_PO_DynamicConfigs", configs[0].name)
    return frappe._dict({
        "name": doc.name,
        "dynamic_url": doc.get_password("dynamic_url", raise_exception=False),
        "access_token_url": doc.get_password("access_token_url", raise_exception=False),
        "client_id": doc.get_password("client_id", raise_exception=False),
        "client_secret": doc.get_password("client_secret", raise_exception=False),
        "dynamic_resource_url": doc.get_password("dynamic_resource_url", raise_exception=False),
        "dynamic_account_url": doc.get_password("dynamic_account_url", raise_exception=False),
        "dynamic_update_account_url": doc.get_password("dynamic_update_account_url", raise_exception=False),
        "dynamic_document_url": doc.get_password("dynamic_document_url", raise_exception=False),
    })


def get_dynamic_accesstoken(dynamic_cnf):

    if dynamic_cnf:
        endpoint = str(dynamic_cnf.access_token_url)
        secrets = [dynamic_cnf.client_id, dynamic_cnf.client_secret]

        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        data = f'grant_type=client_credentials&client_id={dynamic_cnf.client_id}&client_secret={dynamic_cnf.client_secret}&resource={quote_plus(dynamic_cnf.dynamic_resource_url)}'

        response = None
        try:
            response = make_post_request(endpoint, data=data, headers=headers)
        except Exception as e:
            log_dynamics_error(
                "get_dynamic_accesstoken",
                endpoint=endpoint,
                http_method="POST",
                request_data=data,
                response=response,
                exception=e,
                extra_info="Error al obtener access token de Dynamics",
                secrets=secrets,
            )
            raise e
        else:
            token = response.get("access_token") if isinstance(response, dict) else None
            if not token:
                log_dynamics_error(
                    "get_dynamic_accesstoken",
                    endpoint=endpoint,
                    http_method="POST",
                    request_data=data,
                    response=response,
                    extra_info="Dynamics no retornó access_token en la respuesta",
                    secrets=secrets,
                )
            return token


@frappe.whitelist()
def update_dynamics(**args):
    """Wrapper de compatibilidad para llamadas previas a update_dynamics."""
    return call_dynamic(
        beneficiary_id=args.get("beneficiary_id") or args.get("name"),
        id_dynamics=args.get("id_dynamics"),
    )


@frappe.whitelist()
def call_dynamic(beneficiary_id=None, name=None, id_dynamics=None):
    """Envía o actualiza la información del beneficiario en Dynamics CRM (portal y botón del DocType)."""
    endpoint = None
    all_data = None
    response = None
    user = beneficiary_id or name

    try:
        dynamic_cnf = get_dynamic_config()

        if not user:
            log_dynamics_error(
                "call_dynamic",
                extra_info=f"Error al obtener datos del beneficiario: beneficiary_id ({user}) no existe",
            )
            return False

        beneficiary_data = frappe.db.get_value('qp_PO_Beneficiario', user, '*', as_dict=1)

        if not beneficiary_data:
            log_dynamics_error(
                "call_dynamic",
                extra_info=f"No se encontró qp_PO_Beneficiario para {user}",
            )
            return False

        if not dynamic_cnf:
            log_dynamics_error(
                "call_dynamic",
                extra_info=f"No existe configuración en qp_PO_DynamicConfigs | Beneficiario: {beneficiary_data.name}",
            )
            return False

        # Solo actualiza id_dynamics si se envió explícitamente (desde el DocType) y cambió
        if id_dynamics is not None and str(id_dynamics).strip() != "":
            if id_dynamics != beneficiary_data.id_dynamics:
                frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, 'id_dynamics', id_dynamics)
            beneficiary_data.id_dynamics = id_dynamics

        if not beneficiary_data.id_dynamics:
            log_dynamics_error(
                "call_dynamic",
                extra_info=f"El beneficiario {beneficiary_data.name} no tiene id_dynamics asignado",
            )
            return False

        contact_data = frappe.db.get_value("Contact", {'user': beneficiary_data.email}, '*', as_dict=1)

        document_id_qlip = ""
        if contact_data:
            id_supplier = contact_data.name.split("-")[-1]
            supplier_data = frappe.db.get_value('Supplier', {'supplier_name': id_supplier}, '*', as_dict=1)
            if supplier_data:
                document_id_qlip = supplier_data.tax_id

        # Solicitud de Stonex
        if document_id_qlip != beneficiary_data.document_number:
            score = 100
            notas_jumio = "Documento diferente"
        else:
            score = int(beneficiary_data.jumio_points or 0)
            notas_jumio = beneficiary_data.jumio_rejects

        api_token = get_dynamic_accesstoken(dynamic_cnf)

        endpoint = dynamic_cnf.dynamic_url.format(beneficiary_data.id_dynamics)

        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }

        data_document_type = ""
        if beneficiary_data.document_type:
            document_type = frappe.db.get_value('qp_PO_DocumentType', {'do_name': beneficiary_data.document_type}, '*', as_dict=1)
            if document_type:
                data_document_type = document_type.do_code

        # Validación: Si no viene el tipo de documento o es nulo, buscar y asignar OTHER_ID
        if not data_document_type:
            document_type_other = frappe.db.get_value('qp_PO_DocumentType', {'do_name': 'OTHER_ID'}, '*', as_dict=1)
            if document_type_other:
                data_document_type = document_type_other.do_code

        data_city = ""
        if beneficiary_data.city:
            get_city = frappe.db.get_value('qp_PO_City', {'ci_code': beneficiary_data.city}, '*', as_dict=1)
            if get_city:
                data_city = get_city.ci_guid_code

        data_place_birth = ""
        if beneficiary_data.country_of_birth:
            get_country = frappe.db.get_value('qp_PO_Country', {'co_code': beneficiary_data.country_of_birth}, '*', as_dict=1)
            if get_country:
                data_place_birth = get_country.co_guid_code

        data_deparment_birth = ""
        if beneficiary_data.department_of_birth:
            get_department_birth = frappe.db.get_value('qp_PO_TerritorialUnit', {'tu_code': beneficiary_data.department_of_birth}, '*', as_dict=1)
            if get_department_birth:
                data_deparment_birth = get_department_birth.tu_guid_code

        data_city_birth = ""
        if beneficiary_data.city_of_birth:
            get_city = frappe.db.get_value('qp_PO_City', {'ci_code': beneficiary_data.city_of_birth}, '*', as_dict=1)
            if get_city:
                data_city_birth = get_city.ci_guid_code

        data_business = ""
        data_industrial_sector = ""
        if beneficiary_data.business_activity:
            get_bussines_sector = frappe.db.get_value('qp_PO_BusinessActivity', {'ba_code': beneficiary_data.business_activity}, '*', as_dict=1)
            if get_bussines_sector:
                data_business = get_bussines_sector.ba_code
                data_industrial_sector = get_bussines_sector.ba_industrial_sector

        data_parent_name = beneficiary_data.parent_name[0:100] if beneficiary_data.peps_parent and beneficiary_data.parent_name is not None else ''
        data_position = (beneficiary_data.position or "")[0:100]
        data_date = beneficiary_data.link_date.strftime("%Y-%m-%d") if beneficiary_data.link_date is not None else ''
        data_undate = beneficiary_data.link_undate.strftime("%Y-%m-%d") if beneficiary_data.link_undate is not None else ''
        data_date_now = datetime.now()

        # Solicitud de Stonex: incluye ciudad y país de expedición si ambos existen
        if beneficiary_data.document_expedition_city and beneficiary_data.document_expedition_country:
            place_expedition_id = f'{beneficiary_data.document_expedition_city}, {beneficiary_data.document_expedition_country}'
        else:
            place_expedition_id = beneficiary_data.document_expedition_city

        data = {
            "name": f'{beneficiary_data.be_name} {beneficiary_data.surname}',
            "bit_genero": gender_switch(beneficiary_data.gender),
            "bit_tipo_de_documento": data_document_type if data_document_type != "" else None,
            "bit_numero_documento_jumio": beneficiary_data.document_number if beneficiary_data.document_number is not None else "",
            "bit_lugarexpedicion": place_expedition_id if place_expedition_id is not None else "",
            "bit_lugar_de_nacimiento_jumio": beneficiary_data.jumio_place_birth if beneficiary_data.jumio_place_birth is not None else "",
            "bit_Ciudad@odata.bind": f'/bit_ciudads({data_city})',
            "bit_Pais_Nacimiento@odata.bind": f'/bit_pases({data_place_birth})',
            "bit_Lugar_Nacimiento@odata.bind": f'/bit_ciudads({data_city_birth})',
            "bit_Estado_Nacimiento@odata.bind": f'/bit_departamentos({data_deparment_birth})',
            "bit_nacionalidad": (beneficiary_data.nationality or "").upper(),
            "telephone3": beneficiary_data.phone,
            "bit_persona_politicamente_expuesta": isBoolean(beneficiary_data.peps),
            "bit_parentescoconpep": isBoolean(beneficiary_data.peps_parent),
            "bit_salario": beneficiary_data.income,
            "revenue": beneficiary_data.assets,
            "bit_otros_rendimientos": beneficiary_data.egress,
            "bit_pasivo": beneficiary_data.passive,
            "bit_patrimonio_nuevo": beneficiary_data.patrimony,
            "bit_origendelosrecursosarecibir": beneficiary_data.source_fund,
            "bit_score_jumio": score,
            "bit_notas_jumio": notas_jumio,
            "bit_nada": data_business,
            "bit_sectorindustrial": data_industrial_sector,
            "bit_fechacorteinformacionfinanciera": data_date_now.strftime("%Y-%m-%d"),
            "bit_canal": 913610001,
            "bit_documento_identificacion": beneficiary_data.jumio_file,
            "bit_formulario_vinculacion": beneficiary_data.jumio_file
        }

        # Data Empty
        if beneficiary_data.birthday:
            data["bit_fecha_nacimiento"] = beneficiary_data.birthday.strftime("%Y-%m-%d")

        if beneficiary_data.document_expedition_date:
            data["bit_fecha_expedicion_documento"] = beneficiary_data.document_expedition_date.strftime("%Y-%m-%d")

        if data_position:
            data["bit_cargo"] = ''.join(data_position)

        if data_date:
            data["bit_fechavinculacionalargo"] = data_date

        if data_undate:
            data["bit_fechadesvinculacionalcargo"] = data_undate

        if data_parent_name:
            data["bit_nombredelpeprelacionado"] = data_parent_name

        if beneficiary_data.parent_type:
            data["bit_tipoparentezco"] = beneficiary_data.parent_type

        # Send Attach: si envía adjunto, sendDocumentDynamics incrementa el intento y sum_attemp pasa a False
        sum_attemp = True
        if beneficiary_data.document_attach or frappe.db.exists('File', {'attached_to_name': beneficiary_data.name}):
            sendDocumentDynamics(beneficiary_data, dynamic_cnf, api_token)
            sum_attemp = False

        if beneficiary_data.economic_activity:
            economic_data = frappe.db.get_value('qp_PO_EconomicActivity', {'ea_code': beneficiary_data.economic_activity}, '*', as_dict=1)
            if economic_data:
                data["bit_ClaseActividadEconomica@odata.bind"] = f'/bit_claseeconmicas({economic_data.ea_guid})'

        data_address = {
            "address1_line1": beneficiary_data.address
        }

        all_data = json.dumps(data)
        address_payload = json.dumps(data_address)

        response = requests.request("PATCH", endpoint, data=all_data, headers=headers)

        response_address = None
        try:
            response_address = requests.request("PATCH", endpoint, data=address_payload, headers=headers)
            if response_address is not None and not response_address.ok:
                log_dynamics_error(
                    "call_dynamic",
                    endpoint=endpoint,
                    http_method="PATCH",
                    request_data=address_payload,
                    response=response_address,
                    extra_info=f"Error actualizando dirección | Beneficiario: {beneficiary_data.name}",
                )
        except Exception as exe:
            log_dynamics_error(
                "call_dynamic",
                endpoint=endpoint,
                http_method="PATCH",
                request_data=address_payload,
                response=response_address,
                exception=exe,
                extra_info=f"Excepción actualizando dirección | Beneficiario: {beneficiary_data.name}",
            )

        if response:
            saveRequestResponseDynamics(beneficiary_data, all_data, response, "send_status", "query", "response", sum_attemp)

            # Update cuenta bancaria
            get_bank_account(beneficiary_data, dynamic_cnf, api_token, beneficiary_data.id_dynamics, beneficiary_data.account_number)
            return True
        else:
            log_dynamics_error(
                "call_dynamic",
                endpoint=endpoint,
                http_method="PATCH",
                request_data=all_data,
                response=response,
                extra_info=f"Error HTTP guardando beneficiario en Dynamics | Beneficiario: {beneficiary_data.name}",
            )
            saveRequestResponseDynamics(beneficiary_data, all_data, response, "send_status", "query", "response", sum_attemp)
            return False

    except Exception as e:
        log_dynamics_error(
            "call_dynamic",
            endpoint=endpoint,
            http_method="PATCH" if endpoint else None,
            request_data=all_data,
            response=response,
            exception=e,
            extra_info=f"Error general enviando beneficiario a Dynamics | Beneficiario: {user}",
        )
        return False


def get_bank_account(beneficiary, dynamics_conf, token, id_dynamics, account_last_numbers):

    headers = {
        "Authorization": f"Bearer {token}"
    }

    endpoint = dynamics_conf.dynamic_account_url
    endpoint = endpoint.format(id_dynamics, account_last_numbers)

    response = None
    try:
        response = requests.get(endpoint, headers=headers)
        if response:
            data = response.json()

            if len(data.get('value', [])) > 0:
                saveRequestResponseDynamics(beneficiary, endpoint, response, "send_status_account_bank", "query_account_bank", "response_account_bank", False)

                # Send code type account
                id_bancario = data.get('value')[0].get('bit_datos_bancariosid')
                update_banking_dato(beneficiary, dynamics_conf, token, id_bancario)
            else:
                saveRequestResponseDynamics(beneficiary, endpoint, response, "send_status_account_bank", "query_account_bank", "response_account_bank", False)

            return True
        else:
            log_dynamics_error(
                "get_bank_account",
                endpoint=endpoint,
                http_method="GET",
                response=response,
                extra_info=f"Error HTTP consultando cuenta bancaria | Beneficiario: {beneficiary.name}",
            )
            saveRequestResponseDynamics(beneficiary, endpoint, response, "send_status_account_bank", "query_account_bank", "response_account_bank", False)
            return False
    except Exception as e:
        log_dynamics_error(
            "get_bank_account",
            endpoint=endpoint,
            http_method="GET",
            response=response,
            exception=e,
            extra_info=f"Error al buscar y guardar dato bancario | Beneficiario: {beneficiary.name}",
        )
        return False


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

    parse_data = json.dumps(data)

    response = None
    try:
        response = requests.request("PATCH", endpoint, data=parse_data, headers=headers)
        if response is not None:
            if not response.ok:
                log_dynamics_error(
                    "update_banking_dato",
                    endpoint=endpoint,
                    http_method="PATCH",
                    request_data=parse_data,
                    response=response,
                    extra_info=f"Error HTTP actualizando dato bancario | Beneficiario: {beneficiary.name} | Cuenta ID: {id_account}",
                )
            saveRequestResponseDynamics(beneficiary, parse_data, response, "send_status_dato", "query_dato", "response_dato", False)
            return bool(response.ok)
        return False
    except Exception as e:
        log_dynamics_error(
            "update_banking_dato",
            endpoint=endpoint,
            http_method="PATCH",
            request_data=parse_data,
            response=response,
            exception=e,
            extra_info=f"Error actualizando dato bancario | Beneficiario: {beneficiary.name} | Cuenta ID: {id_account}",
        )
        return False


def sendDocumentDynamics(beneficiary, dynamics_conf, token):

    doc_attach = None
    files = frappe.db.get_all(
        'File',
        filters={'attached_to_name': beneficiary.name},
        fields=['*'],
        order_by='creation desc',
        limit=1
    )
    if files:
        doc_attach = files[0]
        if not beneficiary.get("document_attach"):
            frappe.db.set_value('qp_PO_Beneficiario', beneficiary.name, 'document_attach', 1)

    if doc_attach:
        doc_extension = extFile(doc_attach.file_name.split(".")[-1].lower())

        raw_content = frappe.get_doc("File", doc_attach.name).get_content()
        if isinstance(raw_content, string_types):
            raw_content = raw_content.encode("utf-8")
        doc_content = base64.b64encode(raw_content)

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

        all_data = json.dumps(data)

        response = None
        try:
            response = requests.request("POST", endpoint, data=all_data, headers=headers)
            if response is not None:
                if not response.ok:
                    log_dynamics_error(
                        "sendDocumentDynamics",
                        endpoint=endpoint,
                        http_method="POST",
                        request_data=all_data,
                        response=response,
                        extra_info=f"Error HTTP enviando documento a Dynamics | Beneficiario: {beneficiary.name} | Archivo: {doc_attach.file_name}",
                    )
                saveRequestResponseDynamics(beneficiary, all_data, response, "send_status_attach", "query_attach", "response_attach", True)
                return bool(response.ok)
            return False
        except Exception as e:
            log_dynamics_error(
                "sendDocumentDynamics",
                endpoint=endpoint,
                http_method="POST",
                request_data=all_data,
                response=response,
                exception=e,
                extra_info=f"Error al enviar documento a Dynamics | Beneficiario: {beneficiary.name} | Archivo: {doc_attach.file_name}",
            )
            return False


def saveRequestResponseDynamics(beneficiary, request, response, doc_status_code, doc_request, doc_response, doc_attemps):

    try:
        send_date = datetime.now()
        if frappe.db.exists("qp_PO_DynamicsAttemps", {"parent": beneficiary.name}):
            dynamics_attemps = frappe.db.get_value("qp_PO_DynamicsAttemps", {"parent": beneficiary.name}, '*', as_dict=1)

            if doc_attemps:
                frappe.db.set_value('qp_PO_DynamicsAttemps', dynamics_attemps.name, "attemps_num", dynamics_attemps.attemps_num + 1)

            frappe.db.set_value('qp_PO_DynamicsAttemps', dynamics_attemps.name, "send_date", send_date)
            frappe.db.set_value('qp_PO_DynamicsAttemps', dynamics_attemps.name, doc_status_code, response.status_code)
            frappe.db.set_value('qp_PO_DynamicsAttemps', dynamics_attemps.name, doc_request, request)
            frappe.db.set_value('qp_PO_DynamicsAttemps', dynamics_attemps.name, doc_response, response.content)
        else:
            ja = frappe.get_doc({
                "doctype": "qp_PO_DynamicsAttemps",
                "parent": beneficiary.name,
                "parentfield": "dynamics_attemps",
                "parenttype": "qp_PO_Beneficiario",
                "attemps_num": 1,
                "send_date": send_date,
                doc_status_code: response.status_code,
                doc_request: request,
                doc_response: response.content
            })

            ja.insert()

        frappe.db.commit()
    except Exception as e:
        log_dynamics_error(
            "saveRequestResponseDynamics",
            request_data=request,
            response=response,
            exception=e,
            extra_info=f"Error guardando historial en beneficiario {beneficiary.name}",
        )


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
    if not extension:
        return "application/octet-stream"
    extension = extension.lower()
    if extension == "png":
        return "image/png"
    elif extension == "jpeg" or extension == "jpg":
        return "image/jpeg"
    elif extension == "pdf":
        return "application/pdf"
    return "application/octet-stream"