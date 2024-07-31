$( document ).ready(function() {
    $("#basic_data_sect").hide();
    $("#comprobation_sect").hide();

    $("#basic_data_btn").on( "click", function() {
        $("#basic_data_sect").show();
        $("#comprobation_sect").hide();

        frappe.call({
            method: "/",
            args: {},
            success: function(r) {},
            error: function(r) {},
            always: function(r) {},
            btn: opts.btn,
            freeze: false,
            freeze_message: "",
            async: true,
            url: "" || frappe.request.url,
        });
    } );

    $("#comprobation_btn").on( "click", function() {
        $("#basic_data_sect").hide();
        $("#comprobation_sect").show();
    } );


});
