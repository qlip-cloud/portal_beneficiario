import frappe
import os, re
import json
from frappe import _
import frappe.sessions
from six import string_types
from frappe.utils import flt, getdate
from . import constantes


ALLOWED_FILE_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
MAX_BENEFICIARY_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
FILE_MAGIC_BYTES = {
    "pdf": b"%PDF-",
    "png": b"\x89PNG\r\n\x1a\n",
    "jpg": b"\xff\xd8\xff",
    "jpeg": b"\xff\xd8\xff",
}
PHONE_REGEX = re.compile(r"^[0-9+\-\s()]{5,20}$")


def _require_authenticated_user():
    """Bloquea el acceso anónimo (Guest) en endpoints del portal."""
    if frappe.session.user == "Guest":
        frappe.throw(_("No autorizado"), frappe.PermissionError)


def _get_session_beneficiary():
    """Obtiene el documento qp_PO_Beneficiario únicamente desde el email de la sesión autenticada."""
    _require_authenticated_user()

    user_email = frappe.db.get_value("User", frappe.session.user, "email")
    if not user_email:
        frappe.throw(_("Usuario no válido"), frappe.PermissionError)

    beneficiary_name = frappe.db.get_value("qp_PO_Beneficiario", {"email": user_email}, "name")
    if not beneficiary_name:
        frappe.throw(_("Beneficiario no encontrado"), frappe.PermissionError)

    return frappe.get_doc("qp_PO_Beneficiario", beneficiary_name)


def get_beneficiary_permission_query_conditions(user=None):
    """Hook permission_query_conditions: restringe a los Website User estrictamente a su propio qp_PO_Beneficiario."""
    if not user:
        user = frappe.session.user

    if user == "Administrator":
        return ""

    if user == "Guest":
        return "1=0"

    user_info = frappe.db.get_value("User", user, ["user_type", "email"], as_dict=1)
    if not user_info:
        return "1=0"

    if user_info.user_type == "Website User":
        if not user_info.email:
            return "1=0"
        escaped_email = frappe.db.escape(user_info.email.strip().lower())
        return f"LOWER(`tabqp_PO_Beneficiario`.`email`) = {escaped_email}"

    return ""


def has_beneficiary_permission(doc, ptype="read", user=None):
    """Hook has_permission: permite a Website User solo lectura/escritura sobre su propio qp_PO_Beneficiario."""
    if not user:
        user = frappe.session.user

    if user == "Administrator":
        return True

    if user == "Guest":
        return False

    user_info = frappe.db.get_value("User", user, ["user_type", "email"], as_dict=1)
    if not user_info:
        return False

    if user_info.user_type == "Website User":
        if ptype not in ("read", "write"):
            return False

        if not user_info.email:
            return False

        if isinstance(doc, string_types):
            doc_email = frappe.db.get_value("qp_PO_Beneficiario", doc, "email")
        else:
            doc_email = doc.get("email") if doc else None

        if not doc_email:
            return False

        return user_info.email.strip().lower() == str(doc_email).strip().lower()

    return True


def _validate_max_length(value, max_len, label):
    """Valida que una cadena no supere la longitud máxima permitida."""
    if value is not None and len(str(value).strip()) > max_len:
        frappe.throw(
            _("El campo {0} excede la longitud máxima permitida ({1} caracteres).").format(label, max_len),
            frappe.ValidationError,
        )


def _validate_catalog_value(doctype, fieldname, value, label):
    """Verifica que un código recibido desde el cliente exista en su DocType catálogo maestro."""
    if value in (None, ""):
        return
    if not frappe.db.exists(doctype, {fieldname: value}):
        frappe.throw(
            _("Valor no válido para el campo {0}.").format(label),
            frappe.ValidationError,
        )


def _validate_file_content(file_doc):
    """Valida privacidad, extensión, tamaño máximo y magic bytes de un archivo adjunto a qp_PO_Beneficiario."""
    if not file_doc.is_private and not (file_doc.file_url or "").startswith("/private/files/"):
        frappe.throw(_("Los documentos del beneficiario deben ser archivos privados."), frappe.ValidationError)

    file_name = (file_doc.file_name or "").strip()
    ext = os.path.splitext(file_name)[1].lstrip(".").lower()
    if ext not in ALLOWED_FILE_EXTENSIONS:
        frappe.throw(_("Tipo de archivo no permitido. Solo se aceptan PDF, JPG, JPEG o PNG."), frappe.ValidationError)

    raw_content = file_doc.get_content()
    if isinstance(raw_content, string_types):
        raw_content = raw_content.encode("utf-8", errors="ignore")

    if not raw_content or len(raw_content) > MAX_BENEFICIARY_FILE_SIZE:
        frappe.throw(
            _("El archivo está vacío o supera el tamaño máximo permitido (5 MB)."),
            frappe.ValidationError,
        )

    expected_signature = FILE_MAGIC_BYTES.get(ext)
    if expected_signature and not raw_content.startswith(expected_signature):
        frappe.throw(
            _("El contenido del archivo no coincide con un formato válido (PDF, JPG o PNG)."),
            frappe.ValidationError,
        )


def validate_beneficiary_file(doc, method=None):
    """Hook doc_events['File']['validate'] para validar archivos subidos a qp_PO_Beneficiario."""
    if doc.attached_to_doctype != "qp_PO_Beneficiario":
        return

    _require_authenticated_user()

    if doc.attached_to_name and not frappe.has_permission("qp_PO_Beneficiario", ptype="write", doc=doc.attached_to_name):
        session_beneficiary = _get_session_beneficiary()
        if doc.attached_to_name != session_beneficiary.name:
            frappe.throw(_("No tiene permisos para adjuntar archivos a este beneficiario."), frappe.PermissionError)

    _validate_file_content(doc)


@frappe.whitelist()
def save_beneficiary(**args):
    # Se procede a guardar el beneficiario de la sesión activa (prevención de IDOR)
    try:
        b = _get_session_beneficiary()

        # Validación de longitudes y formato básico en servidor
        phone = str(args.get('phone') or "").strip()
        if phone and not PHONE_REGEX.match(phone):
            frappe.throw(_("El número de celular no tiene un formato válido."), frappe.ValidationError)

        address = str(args.get('address') or "").strip()
        pep_position = str(args.get('pep_position') or "").strip()
        fpep_name = str(args.get('fpep_name') or "").strip()

        _validate_max_length(phone, 20, "Celular")
        _validate_max_length(address, 150, "Dirección Residencia")
        _validate_max_length(pep_position, 200, "Cargo PEP")
        _validate_max_length(fpep_name, 140, "Nombre del Familiar PEP")

        # Validación de códigos contra catálogos maestros
        catalog_checks = [
            ("qp_PO_Country", "co_code", args.get('country'), "País de Residencia"),
            ("qp_PO_TerritorialUnit", "tu_code", args.get('department'), "Departamento de Residencia"),
            ("qp_PO_City", "ci_code", args.get('city'), "Ciudad de Residencia"),
            ("qp_PO_Nationality", "na_code", args.get('nationality'), "Nacionalidad"),
            ("qp_PO_Country", "co_code", args.get('country_birth'), "País de Nacimiento"),
            ("qp_PO_TerritorialUnit", "tu_code", args.get('department_birth'), "Departamento de Nacimiento"),
            ("qp_PO_City", "ci_code", args.get('city_birth'), "Ciudad de Nacimiento"),
            ("qp_PO_BusinessActivity", "ba_code", args.get('business_type'), "Actividad Laboral"),
            ("qp_PO_SourceFund", "sf_code", args.get('source_fund'), "Origen de los recursos"),
            ("qp_PO_AccountType", "at_code", args.get('type_account'), "Tipo de cuenta"),
        ]
        for doctype, fieldname, value, label in catalog_checks:
            _validate_catalog_value(doctype, fieldname, value, label)

        if args.get('business_type') == constantes.CODIGO_INDEPENDIENTE:
            _validate_catalog_value("qp_PO_EconomicActivity", "ea_code", args.get('business'), "Actividad Económica")

        if int(args.get('fpep') or 0) == 1:
            _validate_catalog_value("qp_PO_ParentType", "pt_code", args.get('parent_type'), "Tipo de Parentesco")

        b.phone = phone
        b.nationality = args.get('nationality').upper() if args.get('nationality') else ""
        b.address = address.upper() if address else ""
        b.country = args.get('country')
        b.city = args.get('city').upper() if args.get('city') else ""
        b.department = args.get('department')
        b.country_of_birth = args.get('country_birth')
        b.department_of_birth = args.get('department_birth')
        b.city_of_birth = args.get('city_birth')
        b.business_activity = args.get('business_type')

        # Economic validations
        business_map = {
            constantes.CODIGO_INDEPENDIENTE: args.get('business'),
            constantes.CODIGO_EMPLEADO: constantes.ECONOMIC_CODIGO_EMPLEADO,
            constantes.CODIGO_RENTISTA: constantes.ECONOMIC_CODIGO_RENTISTA,
            constantes.CODIGO_PENSIONADO: constantes.ECONOMIC_CODIGO_PENSIONADO
        }

        b.economic_activity = business_map.get(args.get('business_type'), "")

        doc_file_arg = args.get('document_file')
        if doc_file_arg and isinstance(doc_file_arg, string_types) and doc_file_arg.startswith('/private/files/'):
            matched_file = frappe.db.get_value(
                "File",
                {
                    "file_url": doc_file_arg,
                    "attached_to_doctype": "qp_PO_Beneficiario",
                    "attached_to_name": b.name,
                },
                "name",
            )
            if matched_file:
                _validate_file_content(frappe.get_doc("File", matched_file))
                b.document_file = doc_file_arg

        existing_file_url = frappe.db.get_value("File", {"attached_to_name": b.name}, "file_url")
        if not b.document_file and existing_file_url:
            b.document_file = existing_file_url

        if str(args.get('document_send')).lower() in ("true", "1") or b.document_file or existing_file_url:
            b.document_attach = 1

        b.peps = args.get('pep')
        # Peps validations
        if int(args.get('pep') or 0) == 1:
            b.position = pep_position.upper() if pep_position else ""
            b.link_date = getdate(args.get('link_date')) if args.get('link_date') else ""
            b.link_undate = getdate(args.get('link_undate')) if args.get('link_undate') else ""
        else:
            b.position = ""
            b.link_date = ""
            b.link_undate = ""

        b.peps_parent = args.get('fpep')
        # Peps Family
        if int(args.get('fpep') or 0) == 1:
            b.parent_name = fpep_name.upper() if fpep_name else ""
            b.parent_type = args.get('parent_type') if args.get('parent_type') else ""
        else:
            b.parent_name = ""
            b.parent_type = ""

        # Validación en servidor de campos numéricos financieros (no se permiten valores negativos)
        financial_fields = {
            "income": args.get('in'),
            "egress": args.get('out'),
            "assets": args.get('assets'),
            "passive": args.get('passive'),
        }
        for field_name, raw_value in financial_fields.items():
            numeric_value = flt(raw_value)
            if numeric_value < 0:
                frappe.throw(
                    _("Los valores financieros no pueden ser negativos."),
                    frappe.ValidationError,
                )
            setattr(b, field_name, numeric_value)

        b.data_declaration = args.get('term_conditions') if args.get('term_conditions') else 1
        b.authorization_declaration = args.get('term_conditions') if args.get('term_conditions') else 1
        # No se sobrescribe b.email desde el cliente
        b.source_fund = args.get('source_fund').upper() if args.get('source_fund') else ""
        b.account_type = args.get('type_account').upper() if args.get('type_account') else ""

        b.save()
        frappe.db.commit()

        # Retorno mínimo requerido por el frontend
        return {
            "name": b.name,
            "jumio_status": b.jumio_status,
        }

    except (frappe.ValidationError, frappe.PermissionError):
        raise
    except Exception as exe:
        frappe.log_error(
            title='Excepcion en save_beneficiary()',
            message=f'save_beneficiary() - Error guardando beneficiario ({frappe.session.user}): {exe}\n{frappe.get_traceback()}',
        )
        frappe.throw(_("No fue posible guardar la información del beneficiario. Por favor intente de nuevo o comunique al Administrador."))


@frappe.whitelist()
def set_document_file(name=None, file_url=None, **args):
    try:
        b = _get_session_beneficiary()
        file_url = file_url or args.get("file_url")

        if not file_url or not isinstance(file_url, string_types) or not file_url.startswith("/private/files/"):
            frappe.throw(_("Ruta de archivo no válida."), frappe.ValidationError)

        file_name = frappe.db.get_value(
            "File",
            {
                "file_url": file_url,
                "attached_to_doctype": "qp_PO_Beneficiario",
                "attached_to_name": b.name,
            },
            "name",
        )
        if not file_name:
            frappe.throw(_("El archivo no corresponde al beneficiario autenticado."), frappe.PermissionError)

        _validate_file_content(frappe.get_doc("File", file_name))

        b.document_file = file_url
        b.document_attach = 1
        b.save()
        frappe.db.commit()
        return True
    except (frappe.ValidationError, frappe.PermissionError):
        raise
    except Exception as e:
        frappe.log_error(
            title="Excepcion en set_document_file()",
            message=f"set_document_file() - Error guardando ruta de archivo en beneficiario ({frappe.session.user}): {e}",
        )
        frappe.throw(_("No fue posible asociar el archivo al beneficiario."))


@frappe.whitelist()
def get_status():
    _require_authenticated_user()

    user = frappe.db.get_value("User", frappe.session.user, ["name", "email"], as_dict=1)

    if user and user.email:
        beneficiary_dict = frappe.db.get_value('qp_PO_Beneficiario', {'email': user.email}, ['jumio_status', 'name'], as_dict=1)
        if not beneficiary_dict:
            frappe.log_error(title='Excepcion en get_status()', message=f"get_status() - Beneficiario no encontrado para {user.email}")
            return False

        data_client = {
            'mail': user.email,
            'status': beneficiary_dict.jumio_status
        }

        return data_client
    else:
        frappe.log_error(title='Excepcion en get_status()', message=f"get_status()- Error accediendo al usuario logueado {frappe.session.user}:{user}")
        return False


@frappe.whitelist()
def get_cities(**args):
    _require_authenticated_user()

    code = str(args.get('code') or "").strip()
    if not code:
        return []

    if args.get('is_only_city') == "1":
        values = {"country": code}
        cities = frappe.db.sql("""
                                SELECT ci_code, ci_name
                                FROM `tabqp_PO_City` ci
                                LEFT JOIN `tabqp_PO_TerritorialUnit` ti ON ci_deparment = tu_code
                                WHERE ti.tu_country = %(country)s
                                ORDER BY ci_name ASC
                                LIMIT 500
                              """, values=values, as_dict=1)
    else:
        cities = frappe.db.get_all(
            "qp_PO_City",
            filters={"ci_deparment": code},
            fields=['ci_code', 'ci_name'],
            order_by="ci_name asc",
            limit_page_length=500,
        )

    return cities


@frappe.whitelist()
def get_deparments(**args):
    _require_authenticated_user()

    code = str(args.get('code') or "").strip()
    if not code:
        return []

    deparments = frappe.db.get_all(
        "qp_PO_TerritorialUnit",
        filters={"tu_country": code},
        fields=['tu_code', 'tu_name'],
        order_by="tu_name asc",
        limit_page_length=200,
    )
    return deparments


@frappe.whitelist()
def get_countries(**args):
    _require_authenticated_user()

    term = str(args.get("term") or "").strip()
    if len(term) < 2:
        return []

    str_filter = f'%{term[:50]}%'
    filter_values = {"country": str_filter}
    countries = frappe.db.sql("""
                                SELECT co_code, UPPER(co_name) as co_name
                                FROM `tabqp_PO_Country` co
                                WHERE co.co_name LIKE %(country)s
                                ORDER BY co.co_name ASC
                                LIMIT 50
                              """, values=filter_values, as_dict=1)
    return countries