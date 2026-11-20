import frappe
import os, re
import json, datetime
import hmac
import hashlib
from frappe import _
import frappe.sessions
from six import string_types
from frappe.utils import getdate
import base64
import requests
from six import string_types, text_type
from urllib.parse import urlparse
from . import constantes
from . import dynamics


JUMIO_ERROR_PREFIX = "[Jumio Error]"
JUMIO_REQUEST_TIMEOUT = 30
# Cambiar a True cuando se coordine con Jumio la validación de firma, estados e idempotencia del webhook
ENABLE_CALLBACK_SECURITY_CHECKS = False
VALID_CALLBACK_STATUSES = {
    "PROCESSED",
    "SESSION_EXPIRED",
    "TOKEN_EXPIRED",
    "FAILED",
    "INITIATED",
    "ACQUIRED",
}
SENSITIVE_KEYS = {
    "client_id",
    "client_secret",
    "access_token",
    "authorization",
    "password",
    "secret",
    "token",
    "presignedurl",
}


def sanitize_sensitive_data(data, secrets=None):
    """Oculta credenciales (client_id, client_secret, Basic/Bearer tokens) antes de guardar en Error Log."""
    if data is None:
        return None

    secret_values = [str(s) for s in (secrets or []) if s]

    if isinstance(data, dict):
        clean = {}
        for key, value in data.items():
            key_lower = str(key).lower()
            if key_lower in SENSITIVE_KEYS:
                clean[key] = "***REDACTED***"
            else:
                clean[key] = sanitize_sensitive_data(value, secrets=secret_values)
        return clean

    if isinstance(data, list):
        return [sanitize_sensitive_data(item, secrets=secret_values) for item in data]

    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="replace")

    if isinstance(data, str):
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

        sanitized = re.sub(
            r'(?i)(client_id|client_secret|access_token|password|secret)=([^&\s"\']+)',
            r'\1=***REDACTED***',
            data,
        )
        sanitized = re.sub(
            r'(?i)((?:Bearer|Basic)\s+)([^\s"\']+)',
            r'\1***REDACTED***',
            sanitized,
        )
        for secret_val in secret_values:
            sanitized = sanitized.replace(secret_val, "***REDACTED***")
        return sanitized

    return data


def parse_jumio_error(response):
    """Extrae error y código cuando vienen en la respuesta JSON de Jumio."""
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

    result = {}

    # Formato OAuth: {"error": "...", "error_description": "...", "error_codes": [...]}
    if isinstance(payload.get("error"), str):
        result["error"] = payload.get("error")
        error_codes = payload.get("error_codes")
        if isinstance(error_codes, list) and error_codes:
            result["error_codes"] = ", ".join(str(c) for c in error_codes)
        elif error_codes is not None:
            result["error_codes"] = str(error_codes)
        return result

    # Formato API Jumio v4: {"title": "...", "status": 400, "detail": "...", "type": "..."}
    if payload.get("title") or payload.get("detail") or payload.get("message"):
        result["error"] = payload.get("title") or payload.get("message") or payload.get("detail")
        code = payload.get("status") or payload.get("code")
        if code is not None:
            result["error_codes"] = str(code)
        return result

    return None


def log_jumio_error(
    method_name,
    endpoint=None,
    http_method=None,
    request_data=None,
    response=None,
    exception=None,
    extra_info=None,
    secrets=None,
):
    """Registra una sola vez errores de integración con Jumio con título filtrable y datos sanitizados."""
    if exception is not None and getattr(exception, "_jumio_logged", False):
        return None

    if response is None and exception is not None and getattr(exception, "response", None) is not None:
        response = exception.response

    parsed_error = parse_jumio_error(response)

    title = f"{JUMIO_ERROR_PREFIX} {method_name}"
    if parsed_error:
        err_val = parsed_error.get("error")
        codes_val = parsed_error.get("error_codes")
        if err_val and codes_val:
            title = f"{title} - {err_val} ({codes_val})"
        elif err_val:
            title = f"{title} - {err_val}"
        elif codes_val:
            title = f"{title} - {codes_val}"
    title = title[:140]

    parts = [f"Usuario: {frappe.session.user}"]

    if extra_info:
        parts.append(f"Detalle: {sanitize_sensitive_data(str(extra_info), secrets=secrets)}")

    if parsed_error:
        if parsed_error.get("error"):
            parts.append(f"Jumio Error: {sanitize_sensitive_data(str(parsed_error['error']), secrets=secrets)}")
        if parsed_error.get("error_codes"):
            parts.append(f"Jumio Error Codes: {sanitize_sensitive_data(str(parsed_error['error_codes']), secrets=secrets)}")

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
        try:
            exception._jumio_logged = True
        except Exception:
            pass

    frappe.log_error(title=title, message="\n\n".join(parts))
    return parsed_error


def _is_valid_jumio_url(url):
    """Valida que la URL del iframe sea HTTPS y pertenezca a un dominio de Jumio."""
    if not url or not isinstance(url, str):
        return False
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (host == "jumio.ai" or host.endswith(".jumio.ai") or host.endswith(".jumio.com"))


def _verify_jumio_callback_signature(jumio_cnf):
    """Verifica firma HMAC si existe webhook_secret configurado en qp_PO_JumioConfig."""
    webhook_secret = jumio_cnf.get("webhook_secret") if jumio_cnf else None
    if not webhook_secret:
        return True

    signature_header = (
        frappe.get_request_header("X-Jumio-Signature")
        or frappe.get_request_header("x-jumio-signature")
    )
    if not signature_header or not getattr(frappe.request, "data", None):
        return False

    expected = hmac.new(
        webhook_secret.encode("utf-8"),
        frappe.request.data,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header.strip())


def get_jumio_config():
    configs = frappe.db.get_all("qp_PO_JumioConfig", fields=["name"])
    if not configs:
        return None

    doc = frappe.get_doc("qp_PO_JumioConfig", configs[0].name)
    return frappe._dict({
        "name": doc.name,
        "access_token_url": doc.get_password("access_token_url", raise_exception=False),
        "client_id": doc.get_password("client_id", raise_exception=False),
        "client_secret": doc.get_password("client_secret", raise_exception=False),
        "account_url": doc.get_password("account_url", raise_exception=False),
        "retrieval_url": doc.get_password("retrieval_url", raise_exception=False),
        "id_jumio": doc.get_password("id_jumio", raise_exception=False),
        "webhook_secret": doc.get_password("webhook_secret", raise_exception=False) if hasattr(doc, "webhook_secret") else None,
    })


def get_jumio_accesstoken(jumio_cnf):

    if not jumio_cnf:
        return None

    endpoint = jumio_cnf.access_token_url
    credentials = base64.b64encode(f"{jumio_cnf.client_id}:{jumio_cnf.client_secret}".encode()).decode("utf-8")
    secrets = [jumio_cnf.client_id, jumio_cnf.client_secret, credentials]

    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = 'grant_type=client_credentials'

    response = None
    try:
        # Usar requests.post evita el Error Log duplicado de make_post_request y aplica timeout explícito
        response = requests.post(endpoint, data=data, headers=headers, timeout=JUMIO_REQUEST_TIMEOUT)
        if not response.ok:
            log_jumio_error(
                "get_jumio_accesstoken",
                endpoint=endpoint,
                http_method="POST",
                request_data=data,
                response=response,
                extra_info="Error HTTP al obtener access token de Jumio",
                secrets=secrets,
            )
            return None

        payload = response.json()
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not token:
            log_jumio_error(
                "get_jumio_accesstoken",
                endpoint=endpoint,
                http_method="POST",
                request_data=data,
                response=response,
                extra_info="Jumio no retornó access_token en la respuesta",
                secrets=secrets,
            )
        return token
    except Exception as e:
        log_jumio_error(
            "get_jumio_accesstoken",
            endpoint=endpoint,
            http_method="POST",
            request_data=data,
            response=response,
            exception=e,
            extra_info="Excepción al obtener access token de Jumio",
            secrets=secrets,
        )
        return None


@frappe.whitelist()
def get_jumio_iframe():
    """Genera o recupera la URL del iframe de Jumio solo para el beneficiario de la sesión activa."""
    if frappe.session.user == "Guest":
        frappe.throw(_("No autorizado"), frappe.PermissionError)

    endpoint = None
    http_method = None
    data = None
    response = None
    user_email = frappe.session.user

    try:
        jumio_cnf = get_jumio_config()
        user = frappe.db.get_value("User", frappe.session.user, ["name", "email"], as_dict=1)
        if not user or not user.email:
            log_jumio_error(
                "get_jumio_iframe",
                extra_info=f"No se encontró usuario válido para sesión {frappe.session.user}",
            )
            return None

        user_email = user.email
        beneficiary_data = frappe.db.get_value('qp_PO_Beneficiario', {'email': user.email}, '*', as_dict=1)

        if not jumio_cnf or not beneficiary_data:
            log_jumio_error(
                "get_jumio_iframe",
                extra_info=f"Falta configuración de Jumio o registro de beneficiario para {user_email}",
            )
            return None

        if beneficiary_data.jumio_status == "PROCESSED":
            if _is_valid_jumio_url(beneficiary_data.jumio_iframe):
                return {"web": {"href": beneficiary_data.jumio_iframe}}
            return None

        api_token = get_jumio_accesstoken(jumio_cnf)
        if not api_token:
            # El error ya fue registrado en get_jumio_accesstoken()
            return None

        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

        flag_update = False
        endpoint = jumio_cnf.account_url
        http_method = "POST"

        data = json.dumps({
            "customerInternalReference": beneficiary_data.id_dynamics,
            "workflowDefinition": {
                "key": jumio_cnf.id_jumio,
                "capabilities": {
                    "ruleset": {
                        "ids": ["ad18e992-b89a-456d-8dd1-f79622554e15"]
                    }
                }
            }
        })

        if beneficiary_data.jumio_account and beneficiary_data.jumio_workflowexecution:
            endpoint = f'{jumio_cnf.account_url}/{beneficiary_data.jumio_account}'
            http_method = "PUT"
            data = json.dumps({
                "customerInternalReference": beneficiary_data.id_dynamics,
                "workflowDefinition": {
                    "key": jumio_cnf.id_jumio,
                }
            })
            flag_update = True

        if flag_update:
            response = requests.put(endpoint, data=data, headers=headers, timeout=JUMIO_REQUEST_TIMEOUT)
        else:
            response = requests.post(endpoint, data=data, headers=headers, timeout=JUMIO_REQUEST_TIMEOUT)

        if not response.ok:
            log_jumio_error(
                "get_jumio_iframe",
                endpoint=endpoint,
                http_method=http_method,
                request_data=data,
                response=response,
                extra_info=f"Error HTTP solicitando iframe a Jumio | Usuario: {user_email}",
            )
            return None

        payload = response.json()
        workflow_id = (payload.get("workflowExecution") or {}).get("id")
        account_id = (payload.get("account") or {}).get("id")
        iframe_href = (payload.get("web") or {}).get("href")

        if not workflow_id or not account_id or not _is_valid_jumio_url(iframe_href):
            log_jumio_error(
                "get_jumio_iframe",
                endpoint=endpoint,
                http_method=http_method,
                request_data=data,
                response=response,
                extra_info=f"Respuesta incompleta o URL inválida desde Jumio | Usuario: {user_email}",
            )
            return None

        frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "jumio_workflowexecution", workflow_id)
        frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "jumio_account", account_id)
        frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "jumio_iframe", iframe_href)
        frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "enable", 0)
        frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "jumio_status", "PENDING")
        frappe.db.commit()

        # Principio de mínimo privilegio: devolver al frontend únicamente la URL del iframe
        return {"web": {"href": iframe_href}}

    except Exception as e:
        log_jumio_error(
            "get_jumio_iframe",
            endpoint=endpoint,
            http_method=http_method,
            request_data=data,
            response=response,
            exception=e,
            extra_info=f"Error cargando datos de iframe Jumio | Usuario: {user_email}",
        )
        return None


# Función interna (sin @frappe.whitelist para prevenir IDOR y exposición de PII)
def get_jumio_retrieval(beneficiary_id, status_callback, json_callback):

    user = beneficiary_id
    endpoint = None
    endpoint_file = None
    response = None
    response_file = None

    try:
        jumio_cnf = get_jumio_config()
        beneficiary_data = frappe.db.get_value('qp_PO_Beneficiario', user, '*', as_dict=1)

        if not jumio_cnf or not beneficiary_data:
            log_jumio_error(
                "get_jumio_retrieval",
                extra_info=f"Falta configuración de Jumio o beneficiario {user}",
            )
            return False

        rejects_list = []
        data_usability = dict()

        api_token = get_jumio_accesstoken(jumio_cnf)
        if not api_token:
            return False

        endpoint = jumio_cnf.retrieval_url.format(
            beneficiary_data.jumio_account,
            beneficiary_data.jumio_workflowexecution,
        )
        endpoint_file = f'{endpoint}/generate'
        headers = {"Authorization": f"Bearer {api_token}"}

        response = requests.get(endpoint, headers=headers, timeout=JUMIO_REQUEST_TIMEOUT)
        if not response.ok:
            log_jumio_error(
                "get_jumio_retrieval",
                endpoint=endpoint,
                http_method="GET",
                response=response,
                extra_info=f"Error HTTP en retrieval de Jumio | Beneficiario: {beneficiary_data.name}",
            )
            return False

        payload = response.json()

        response_file = requests.get(endpoint_file, headers=headers, timeout=JUMIO_REQUEST_TIMEOUT)
        data_file = {}
        if response_file is not None and response_file.ok:
            data_file = response_file.json()
        else:
            log_jumio_error(
                "get_jumio_retrieval",
                endpoint=endpoint_file,
                http_method="GET",
                response=response_file,
                extra_info=f"Error HTTP obteniendo archivo de Jumio | Beneficiario: {beneficiary_data.name}",
            )

        capabilities = payload.get("capabilities") or {}
        extraction_list = capabilities.get("extraction") or [{}]
        extraction_data = (extraction_list[0] or {}).get("data") or {}

        data_notes = {
            "extraction": (extraction_list[0] or {}).get("decision", {}).get("type"),
            "similarity": ((capabilities.get("similarity") or [{}])[0] or {}).get("decision", {}).get("type"),
            "liveness": ((capabilities.get("liveness") or [{}])[0] or {}).get("decision", {}).get("type"),
            "dataChecks": ((capabilities.get("dataChecks") or [{}])[0] or {}).get("decision", {}).get("type"),
            "imageChecks": ((capabilities.get("imageChecks") or [{}])[0] or {}).get("decision", {}).get("type"),
        }

        if capabilities.get("watchlistScreening"):
            data_notes["watchList"] = capabilities["watchlistScreening"][0].get("decision", {}).get("type")

        for item in data_notes:
            reject_string = get_validation_rejected(item, constantes.VALUE_REJECTS, data_notes)
            if reject_string:
                rejects_list.append(f'{reject_string}')

        for item in (capabilities.get("usability") or []):
            creds = item.get("credentials") or []
            if creds:
                data_usability[creds[0].get("category")] = item.get("decision", {}).get("type")

        for item in data_usability:
            reject_string = get_validation_rejected(item, constantes.VALUE_REJECTS, data_usability)
            if reject_string:
                rejects_list.append(f'usability:{reject_string}')

        rejects_string = ";".join(rejects_list)

        risk_score = ((payload.get("decision") or {}).get("risk") or {}).get("score")
        frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "jumio_points", risk_score)
        frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "jumio_rejects", rejects_string)
        frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "jumio_file", data_file.get("presignedUrl") if isinstance(data_file, dict) else "")
        frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "be_name", extraction_data.get("firstName"))
        frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "surname", extraction_data.get("lastName"))

        if extraction_data.get("type") == constantes.TYPE_DOCUMENT:
            frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "document_type", extraction_data.get("subType"))

        jumio_document = (
            extraction_data.get("optionalMrzField2")
            if extraction_data.get("optionalMrzField2") is not None
            else extraction_data.get("documentNumber")
        )

        frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "document_number", jumio_document)
        frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "gender", extraction_data.get("gender"))
        frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "birthday", extraction_data.get("dateOfBirth"))
        frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "jumio_place_birth", extraction_data.get("placeOfBirth"))
        frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "document_expedition_date", extraction_data.get("issuingDate"))
        frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "document_expedition_city", extraction_data.get("issuingPlace"))
        frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "document_expedition_country", extraction_data.get("issuingCountry"))

        ja = frappe.get_doc({
            "doctype": "qp_PO_JumioAttemps",
            "parent": beneficiary_data.name,
            "parentfield": "jumio_attemps",
            "parenttype": "qp_PO_Beneficiario",
            "jumio_status_workflow": status_callback,
            "jumio_callback_data": json_callback,
            "attemps_num": 1,
            "query": endpoint,
            "response": json.dumps(payload, default=json_handler),
            "jumio_file_status": response_file.status_code if response_file is not None else None,
            "jumio_file_request": endpoint_file,
            "jumio_file_response": response_file.content if response_file is not None else None,
        })
        ja.insert(ignore_permissions=True)
        frappe.db.commit()

        # Enviar actualización a Dynamics CRM
        dynamics.call_dynamic(user)
        return True

    except Exception as e:
        log_jumio_error(
            "get_jumio_retrieval",
            endpoint=endpoint,
            http_method="GET" if endpoint else None,
            response=response,
            exception=e,
            extra_info=f"Error guardando datos de retrieval | Beneficiario: {user}",
        )
        return False


@frappe.whitelist(allow_guest=True)
def callback(**args):
    """Webhook de Jumio. Controles estrictos gobernados por ENABLE_CALLBACK_SECURITY_CHECKS."""
    try:
        workflow = args.get("workflowExecution") or {}
        account = args.get("account") or {}

        if ENABLE_CALLBACK_SECURITY_CHECKS:
            jumio_cnf = get_jumio_config()
            if not _verify_jumio_callback_signature(jumio_cnf):
                log_jumio_error(
                    "callback",
                    request_data=args,
                    extra_info="Firma de webhook Jumio inválida o ausente",
                )
                frappe.local.response["http_status_code"] = 403
                return 1

            if not isinstance(workflow, dict) or not isinstance(account, dict):
                log_jumio_error(
                    "callback",
                    request_data=args,
                    extra_info="Payload de callback inválido: faltan objetos workflowExecution o account",
                )
                frappe.local.response["http_status_code"] = 400
                return 1

        workflow_id = workflow.get("id") if isinstance(workflow, dict) else None
        account_id = account.get("id") if isinstance(account, dict) else None
        status_workflowExecution = workflow.get("status") if isinstance(workflow, dict) else None

        if ENABLE_CALLBACK_SECURITY_CHECKS:
            if not workflow_id or not account_id or status_workflowExecution not in VALID_CALLBACK_STATUSES:
                log_jumio_error(
                    "callback",
                    request_data=args,
                    extra_info=f"Datos inválidos en callback (status={status_workflowExecution})",
                )
                frappe.local.response["http_status_code"] = 400
                return 1

        beneficiary_data = frappe.db.get_value(
            'qp_PO_Beneficiario',
            {'jumio_workflowexecution': workflow_id, 'jumio_account': account_id},
            '*',
            as_dict=1,
        )

        if not beneficiary_data:
            return 1

        # Idempotencia: evitar replay si el beneficiario ya fue procesado
        if ENABLE_CALLBACK_SECURITY_CHECKS and beneficiary_data.jumio_status == "PROCESSED":
            return 0

        json_workflow_format = json.dumps(args, default=json_handler)

        if status_workflowExecution in ["SESSION_EXPIRED", "TOKEN_EXPIRED"]:
            doc = frappe.get_doc({
                "doctype": "qp_PO_JumioAttemps",
                "parent": beneficiary_data.name,
                "parentfield": "jumio_attemps",
                "parenttype": "qp_PO_Beneficiario",
                "jumio_status_workflow": status_workflowExecution,
                "jumio_callback_data": json_workflow_format,
                "attemps_num": 1,
            })
            doc.insert(ignore_permissions=True)

            frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "jumio_status", "PENDING")
            frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "enable", 1)
            frappe.db.commit()
        else:
            frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "jumio_status", status_workflowExecution)
            frappe.db.set_value('qp_PO_Beneficiario', beneficiary_data.name, "enable", 1)
            frappe.db.commit()

            # Retrieval Jumio
            get_jumio_retrieval(beneficiary_data.name, status_workflowExecution, json_workflow_format)

        return 0
    except Exception as e:
        log_jumio_error(
            "callback",
            request_data=args,
            exception=e,
            extra_info="Excepción procesando callback de Jumio",
        )
        return 1


def json_handler(obj):
    if isinstance(obj, (datetime.date, datetime.timedelta, datetime.datetime)):
        return text_type(obj)


def get_validation_rejected(key, values, dictionary):
    for i in range(len(values)):
        if key in dictionary and dictionary[key] and values[i] in dictionary[key]:
            return key, values[i]