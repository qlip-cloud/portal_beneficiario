$( document ).ready(function() {
   
    $("form#pb_form").validate({
        rules:{
            name:'required',
            phone:'required',
            nationality:'required',
            address:'required',
            city:'required',
            business:'required',
            business_type:'required',
            in:{required: true,number: true},
            out:{required: true,number: true},
            assets:{required: true,number: true},
            passive:{required: true,number: true},
            source_fund:'required',
            pep:'required',
            fpep:'required'
        },
        errorClass: "input-error",
        validClass: "input-success",
        errorElement: "div",
        errorLabelContainer: "#messageBox",
        highlight: function(element, errorClass, validClass) {
            $(element).addClass(errorClass);
            $(element).removeClass(validClass);
        },
        unhighlight: function(element, errorClass, validClass) {
            $(element).removeClass(errorClass);
            $(element).addClass(validClass);
        },
        showErrors: function(errorMap, errorList) {
            $("#messageBox").html("Contiene un total de " + this.numberOfInvalids() + " campos requeridos y obligatorios sin completar");

            var i, elements, error;

            for (i = 0; this.errorList[ i ]; i++ ) {
                error = this.errorList[ i ];
                if ( this.settings.highlight ) {
                    this.settings.highlight.call( this, error.element, this.settings.errorClass, this.settings.validClass );
                }
            }

			if ( this.settings.unhighlight ) {
				for ( i = 0, elements = this.validElements(); elements[ i ]; i++ ) {
					this.settings.unhighlight.call( this, elements[ i ], this.settings.errorClass, this.settings.validClass );
				}
			}
        }
    });
    
    if($('#link_date')){
        $('#link_date').datepicker({ dateFormat: 'dd-mm-yy' });
    }

    $('input[type=radio][name=pep]').change(function() {
        if(this.value == '1') {
            $('.pep_fields').removeAttr('hidden');
        }else{
            $('.pep_fields').attr('hidden', true);
        }
    });


    $('input[type=radio][name=fpep]').change(function() {
        if(this.value == '1') {
            $('.fpep_fields').removeAttr('hidden');
        }else{
            $('.fpep_fields').attr('hidden', true);
        }
    });

    $("#term_conditions").change(function (e) {
        if(this.checked) {
            $('#acept_term').removeAttr('disabled');
        }else{
            $('#acept_term').attr('disabled', true);
        }
    });

    $("#acept_term").click(function (e) {
        $('#term_and_codition_btn').attr('hidden', true);
    });

    $("form #step2").change(function (e) {
        if($('#pb_form').valid()){
            $("form #step2").find('button').removeAttr('disabled');
            $('#messageBox').addClass('hidden')
        }else{
            $('#messageBox').removeClass('hidden')
        }
    });

    $("form #step1").ready(function (e) {
        $("#term_conditions").change();
    });

    $("form #step2").ready(function (e) {
        if($("#pb_form").valid()){
            $("form #step2").find('button').removeAttr('disabled');
        }
    });

    $(".next-step").click(function (e) {
        if($('#pb_form').valid()){
            var active = $('.wizard .nav-tabs li.active');
            nextTab(active);
        }      
    });

    $(".prev-step").click(function (e) {
        var active = $('.wizard .nav-tabs li.active');
        prevTab(active);
    });

    $("#finish").click(function (e) {
        alert("Finalizado");   
    });

    $("#save_beneficiary").click(function (e) {

        var unindexed_array = $('#pb_form').serializeArray()
        var indexed_array = {};

        $.map(unindexed_array, function(n, i){
            indexed_array[n['name']] = n['value'];
        });

        $.ajax({
            url: "/api/method/portal_beneficiario.www.home_pb.index.save_beneficiary",
            data:indexed_array,
            dataType: 'json',
            contentType: 'application/json;charset=UTF-8',
            async: false
          }).done(function(r) {
                call_get_service_data(r.message)
          });  
    });

    $("input.number").on('blur', function() {
        const value = this.value.replace(/,/g, '');

        if(!isNaN(parseFloat(this.value))){
            this.value = parseFloat(value).toLocaleString('en-US', {
                style: 'decimal',
                maximumFractionDigits: 2,
                minimumFractionDigits: 2
            });
        }else{
            this.value = 0;
        }
        
      });
});

function nextTab(elem) {
    $(elem).next().find('a[data-toggle="tab"]').click();
}
function prevTab(elem) {
    $(elem).prev().find('a[data-toggle="tab"]').click();
}

function call_get_service_data(data){
    frappe.db.get_list(
        "qp_PO_JumioConfig", 
        {
            fields:["access_token_url", "jumio_service_url", "client_id", "client_secret"]
        }).then((v) => {
            callJumio(v, data,  callAccessToken(v));
        })
}
function callJumio(data, user, token) {

    $.ajax({
        url: data.jumio_service_url,
        method:'POST',
        data:{
            "customerInternalReference":user.id_dynamics,
            "workflowDefinition":{
                "key": user.id_jumio
            }
        },
        dataType: 'json',
        contentType: 'application/json;charset=UTF-8',
        async: false,
        beforeSend: function (xhr) {
            xhr.setRequestHeader('Authorization', `Bearer ${token}`);
        },
    }).done(function(r) {
        console.log(r)
        $('#jumio_iframe').attr('src', r.web.href);
    });
}

function callAccessToken(data){

    var token = "";

    $.ajax({
        url: data.access_token_url,
        method:'GET',
        data: {
            "grant_type": "client_credentials"
        },
        dataType: 'json',
        contentType: 'application/x-www-form-urlencoded',
        async: false,
        username:data.client_id,
        password:data.client_secret
    }).done(function(r) {
        return token = r.access_token
    }).fail(function(r) {
        alert(r);
    });
}

$('.nav-tabs').on('click', 'li', function() {

    var li_active = $('.nav-tabs li.active');
    var div_active = li_active.find('a[data-toggle="tab"]').attr('aria-controls');
    $(`#${div_active}`).removeClass('active');

    $(this).addClass('active');
    $(this).removeClass('disabled');
    $(this).find('a[data-toggle="tab"]').attr('hidden', false);
    var this_div = $(this).find('a[data-toggle="tab"]').attr('aria-controls')
    $(`#${this_div}`).addClass('active');

    li_active.removeClass('active');
});