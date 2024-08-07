import frappe

def get_context(context):

    context["is_navbar_custom"] = True
    return context

@frappe.whitelist()
def save_beneficiary(**args):
    print(args)
    return "intentando guardar"
