import frappe
from qlip_pay_portal.qlip_pay_portal.resources.api.user.login_api import get_access
from qlip_pay_portal.qlip_pay_portal.uses_cases.login.access_role import set_cache_session


def get_home_page(user):

    cache = frappe.cache()

    redirect_to = "/"

    if user == "Administrator":

        redirect_to = "/mentum/companies"

    else:

        result = get_access(user)

        if result.get('status') == 200:

            redirect_to = result.get('redirect_to') or "/"

    if cache.get_value('b2c_login') == frappe.session.user:

        set_cache_session()
        cache.delete_value('b2c_login')

    return redirect_to