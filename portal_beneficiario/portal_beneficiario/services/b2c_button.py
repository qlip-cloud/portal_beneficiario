from frappe.utils.oauth import get_oauth2_authorize_url, get_oauth_keys
import frappe
from frappe.utils.password import get_decrypted_password
from frappe.utils.html_utils import get_icon_html
from frappe.translate import guess_language
from frappe.website.utils import get_home_page
from frappe.integrations.doctype.ldap_settings.ldap_settings import LDAPSettings
from frappe import _
def handler(context):
    
    redirect_to = frappe.local.request.args.get("redirect-to")

    if frappe.session.user != "Guest":
        if not redirect_to:
            if frappe.session.data.user_type=="Website User":
                redirect_to = get_home_page()
            else:
                redirect_to = "/app"

        if redirect_to != 'login':
            frappe.local.flags.redirect_location = redirect_to
            raise frappe.Redirect

    # get settings from site config
    context.no_header = True
    context.for_test = 'login.html'
    context["title"] = "Login"
    context["provider_logins"] = []
    context["disable_signup"] = frappe.utils.cint(frappe.db.get_value("Website Settings", "Website Settings", "disable_signup"))
    context["logo"] = frappe.get_hooks("app_logo_url")[-1]
    context["app_name"] = frappe.get_system_settings("app_name") or _("Frappe")
    providers = [i.name for i in frappe.get_all("Social Login Key", filters={"enable_social_login":1}, order_by="name")]
    for provider in providers:
        client_id, base_url = frappe.get_value("Social Login Key", provider, ["client_id", "base_url"])
        client_secret = get_decrypted_password("Social Login Key", provider, "client_secret")
        provider_name = frappe.get_value("Social Login Key", provider, "provider_name")

        icon = None
        icon_url = frappe.get_value("Social Login Key", provider, "icon")
        if icon_url:
            if provider_name != "Custom":
                icon = "<img src='{0}' alt={1}>".format(icon_url, provider_name)
            else:
                icon = get_icon_html(icon_url, small=True)

        if (get_oauth_keys(provider) and client_secret and client_id and base_url):
            if provider == "office_365":
                # Ajustes para manejar diferentes claves sociales
                # Nueva versión para manejar aplicación de valley floral
                b2c_sign = frappe.get_value('Social Login Key', 'office_365', ['qp_sign_in'])

                context.provider_logins.append({
                    "name": provider,
                    "provider_name": provider_name,
                    "auth_url": get_oauth2_authorize_url(provider, redirect_to)+'&p={0}'.format(b2c_sign),
                    "register_url": get_oauth2_authorize_url(provider, redirect_to)+'&p={0}&prompt=login'.format(b2c_sign),
                    "icon": icon
                })
            else:
                context.provider_logins.append(
                    {
                        "name": provider,
                        "provider_name": provider_name,
                        "auth_url": get_oauth2_authorize_url(provider, redirect_to),
                        "register_url": get_oauth2_authorize_url(provider, redirect_to) + "&prompt=login",
                        "icon": icon,
                    }
                )
            context["social_login"] = True
    ldap_settings = LDAPSettings.get_ldap_client_settings()
    context["ldap_settings"] = ldap_settings

    login_label = [_("Email")]

    if frappe.utils.cint(frappe.get_system_settings("allow_login_using_mobile_number")):
        login_label.append(_("Mobile"))

    if frappe.utils.cint(frappe.get_system_settings("allow_login_using_user_name")):
        login_label.append(_("Username"))

    context['login_label'] = ' {0} '.format(_('or')).join(login_label)

    # ALPHAS
    win_lang = guess_language() or 'es'
    context['qp_lang_en'] = win_lang[0:2] == 'en' and True or False
    #####

    # ALPHAS
    list_apps = frappe.get_installed_apps()
    context['qp_url_register'] = "/register"
    context['qp_pay'] = "qlip_pay_portal" in list_apps and context.get("social_login") and True or False
    #####

    return context