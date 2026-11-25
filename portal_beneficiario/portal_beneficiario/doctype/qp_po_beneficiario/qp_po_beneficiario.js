// Copyright (c) 2024, Adolfo Hernandez and contributors
// For license information, please see license.txt

frappe.ui.form.on('qp_PO_Beneficiario', {
	refresh: function(frm) {
		frm.add_custom_button(__('Actualizar Registro en CRM'), function() {
			const enviar_a_dynamics = function() {
				frappe.call({
					method: 'portal_beneficiario.portal_beneficiario.services.dynamics.call_dynamic',
					args: {
						beneficiary_id: frm.doc.name,
						id_dynamics: frm.doc.id_dynamics
					},
					freeze: true,
					freeze_message: __('Enviando actualización a Dynamics CRM, por favor espere...'),
					callback: function(r) {
						if (r.message) {
							frappe.msgprint({
								title: __('Stonex'),
								indicator: 'green',
								message: __('Documento actualizado satisfactoriamente en Dynamics.')
							});
						} else {
							frappe.msgprint({
								title: __('Stonex'),
								indicator: 'red',
								message: __('No se pudo completar la actualización en Dynamics. Revise el Error Log ([Dynamics Error]) para más detalle.')
							});
						}
						frm.reload_doc();
					}
				});
			};

			// Si hay cambios sin guardar en el formulario, guardar primero para enviar datos actualizados
			if (frm.is_dirty()) {
				frm.save().then(enviar_a_dynamics);
			} else {
				enviar_a_dynamics();
			}
		});
	}
});