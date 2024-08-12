import frappe

def get_home_page(user):

    cache = frappe.cache()
    
    redirect_to = "/"

    if user == "Administrator":
        redirect_to = "/app"
    
    if user != "Guest" and user != "Administrator":
        redirect_to = "/home_pb"

    if cache.get_value('b2c_login') == frappe.session.user:

        cache.delete_value('b2c_login')

    return redirect_to