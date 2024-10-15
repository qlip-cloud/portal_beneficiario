// Copyright (c) 2024, Adolfo Hernandez and contributors
// For license information, please see license.txt

frappe.ui.form.on('qp_PO_Beneficiario', {
	refresh: function(frm) {
		frm.add_custom_button(__('Actualizar'), function(){

			$.ajax({
				url: "/api/method/portal_beneficiario.portal_beneficiario.services.dynamics_update.update_dynamics",
				data: {
					'name': frm.doc.name,
					'id_dynamics': frm.doc.id_dynamics
				},
				dataType: 'json',
				async: false,
				contentType: 'application/json;charset=UTF-8',
			}).done(function(r) {
				
				frappe.msgprint({
					title: 'Stonex',
					message: 'Documento actualizado satisfactoriamente'
				});
				
				frm.reload_doc();
			});
		})
	}
});
