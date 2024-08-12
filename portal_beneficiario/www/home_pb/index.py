import frappe

def get_context(context):

    context["is_navbar_custom"] = True
    return context

@frappe.whitelist()
def save_beneficiary(**args):

    print(**args)
    
    doc_tp = frappe.get_doc({
        'doctype': 'qp_PO_Beneficiario',
        'phone':args.get('phone'),
        'nationality':args.get('nationality'),
        'address':args.get('address'),
        'city':args.get('city'),
        'peps':True if args.get('pepSi') == 1 else False,
        'peps_parent':True if args.get('fpepSi') == 1 else False,
        'income': args.get('in'),
        'egress': args.get('out'),
        'assets':args.get('assets'),
        'passive':args.get('passive')
    })

    doc_tp.insert()

    frappe.db.commit()

    return doc_tp
