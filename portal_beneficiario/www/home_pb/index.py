import frappe

def get_context(context):

    context["is_navbar_custom"] = True
    return context

@frappe.whitelist()
def save_beneficiary(**args):

    doc_tp = frappe.get_doc({
        'doctype': 'qp_PO_Beneficiario',
        'phone':args.get('phone'),
        'nationality':args.get('nationality'),
        'address':args.get('address'),
        'city':args.get('city'),
        'peps':args.get('pep'),
        'peps_parent':args.get('fpep'),
        'income': args.get('in'),
        'egress': args.get('out'),
        'assets':args.get('assets'),
        'passive':args.get('passive')
    })

    doc_tp.insert()

    frappe.db.commit()

    return doc_tp
