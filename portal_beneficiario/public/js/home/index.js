$( document ).ready(function() {
   
    $("form#pb_form").validate({
        debug: false,
        rules:{
            phone: {required: true,number: true, maxlength: 20},
            nationality:'required',
            country_birth: 'required',
            city_birth: 'required',
            address:'required',
            country: 'required',
            city:'required',
            department: 'required',
            business:'required',
            business_type:'required',
            fileToUpload: 'required',
            pep_position: {required:true, maxlength: 200},
            link_date: 'required',
            in:{required: true,number: true},
            out:{required: true,number: true},
            assets:{required: true,number: true},
            passive:{required: true,number: true},
            source_fund:'required',
            pep:'required',
            fpep:'required',
            fpep_name: 'required',
            parent_type: 'required',
            type_account: 'required'
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
            if(errorList.length > 0)
                $("#messageBox").html("Contiene un total de " + this.numberOfInvalids() + " campos requeridos y obligatorios sin completar.");

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

    $("#country").change(function (e) {
        if(this.value != '') {
            $('#department').removeAttr('disabled');

            $.ajax({
                url: "/api/method/portal_beneficiario.portal_beneficiario.services.beneficiary.get_deparments",
                data: {"code": this.value},
                dataType: 'json',
                async: false
            }).done(function(r) {
                if(r.message){          
                    data = r.message;
                    
                    $("#department").empty();
                    $("#department").append("<option></option>");
                    
                    for (var key in data){
                        $("#department").append(`<option value='${data[key].tu_code}'>${data[key].tu_name.toUpperCase()}</option>`);
                    }
        
                } else {
                    alert("Sistema en mantenimiento, disculpe las molestias ocasionadas.");
                } 
            });

        } else {
            $('#department').val('');
            $('#department').attr('disabled', true);
        }
    });

    $("#department").change(function (e) {
        if(this.value != '') {
            $('#city').removeAttr('disabled');
            getCities(this.value, $('#city'), 0);

        } else {
            $('#city').val('');
            $('#city').attr('disabled', true);
        }
    });

    $("#country_birth").change(function (e) {
        if(this.value != '') {
            $('#city_birth').removeAttr('disabled');
            getCities(this.value, $('#city_birth'), 1);

        } else {
            $('#city_birth').val('');
            $('#city_birth').attr('disabled', true);
        }
    });

    $("#modal-buttom").click(function (e) {
        var me = this;
        me.logged_out = true;

        return frappe.call({
            method: "logout",
            callback: function(r){
                if(r.exc){
                     return;
                }
                window.location.replace("https://www.stonexcolombia.com/");
            }
        });
    });

    // Form validate
    validatePositiveNumbers($('#in'));
    validatePositiveNumbers($('#out'));
    validatePositiveNumbers($('#assets'));
    validatePositiveNumbers($('#passive'));

    if($('#link_date')){
        $('#link_date').datepicker({ dateFormat: 'dd-mm-yy' });
    }

    if($('#link_undate')){
        $('#link_undate').datepicker({ dateFormat: 'dd-mm-yy' });
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

    $("#business_type").change(function() {
        if(['913610001','913610003','913610004'].includes(this.value)) {
            
            if(['913610003','913610004'].includes(this.value)){
                $('.activity_fields').removeAttr('hidden');
                $('.business_field').attr('hidden', true);
            } else {
                $('.business_field').removeAttr('hidden');
                $('.activity_fields').removeAttr('hidden');
            }
                
        }else{
            $('.activity_fields').attr('hidden', true);
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

    $("form #step3").ready(function (e) {
        if($("#jumio_iframe").attr("src") != ""){
            checkStatus()
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

    $("#save_beneficiary").click(function (e) {

        var unindexed_array = $('#pb_form').serializeArray()
        var indexed_array = {};

        $.map(unindexed_array, function(n, i){
            indexed_array[n['name']] = n['value'];
        });

        fileToUpload = $('#fileToUpload').prop('files');

        if (fileToUpload.length != 0){
            indexed_array.document_send = true
        }

        $.ajax({
            url: "/api/method/portal_beneficiario.portal_beneficiario.services.beneficiary.save_beneficiary",
            data:indexed_array,
            dataType: 'json',
            contentType: 'application/json;charset=UTF-8',
            async: false
          }).done(function(r) {

                let response = r.message;

                // Upload File        
                if (fileToUpload.length != 0){
                    
                    var formData = new FormData();

                    url_file = "/api/method/upload_file";

                    formData.append("file", fileToUpload[0], fileToUpload[0].name);
                    formData.append("is_private", 0);
                    formData.append("doctype", "qp_PO_Beneficiario");
                    formData.append("docname", response.name);
                    formData.append("fieldname", "document_attach");

                    call_back = (data) => {

                        if(data) {
                            if(r.message.jumio_status != "PROCESSED"){
                                callJumio(r.message)
                            }
                        }
                    }

                    send_petition_upload("", "", formData, call_back, url_file);
                
                } else {
                    if(r.message.jumio_status != "PROCESSED"){
                        callJumio(r.message)
                    }
                }


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

function send_petition_upload(module_root, method, formData, callback, url = null){

    return new Promise((resolve, reject) => {
        let xhr = new XMLHttpRequest();
        xhr.onreadystatechange = () => {
            if (xhr.readyState == XMLHttpRequest.DONE) {
                response = JSON.parse(xhr.responseText);

                if (xhr.status === 200) {                  
                    callback(response.message);
                } else {
                    callback(response.message);   
                    frappe.msgprint(__(`Error: ${response.message.msg}`));
                }
            }
        }

        endpoint = url ? url : setup_api_method(API_ROOT, module_root, method, true);
        
        xhr.open('POST',endpoint , true);
        xhr.setRequestHeader('Accept', 'application/json');
        xhr.setRequestHeader('X-Frappe-CSRF-Token', frappe.csrf_token);
        xhr.send(formData);
    })
}

function setup_api_method(api_root, module_root, method, has_base_root = false){

    base_root = has_base_root ? "/api/method/" : "";
    result = `${ base_root }${api_root}.${module_root}.${metohd}`;
    return result;

}

function callJumio(beneficiary) {

    $.ajax({
        url: "/api/method/portal_beneficiario.portal_beneficiario.services.jumio.get_jumio_iframe",
        dataType: 'json',
        contentType: 'application/json;charset=UTF-8',
      }).done(function(r) {

            if(r.message){
                $('#jumio_iframe').attr('src', r.message.web.href);
                $('#basic_btn').addClass('hidden');
                $("#messageBox").html("¡Gracias por tu paciencia! Estamos validando tu identidad de manera segura. En pocos minutos, todo estará listo.");
                $('#messageBox').removeClass('hidden')
                checkStatus()
            }else{
                alert("Error de comunicación con Jumio");
            }
           
      });
}

function checkStatus(){

    var min = 0;

    var refreshIntervalId = setInterval(()=>{
        
        min+=1;

        $.ajax({
            url: "/api/method/portal_beneficiario.portal_beneficiario.services.beneficiary.get_status",
            dataType: 'json',
            contentType: 'application/json;charset=UTF-8',
          }).done(function(r) {

                if(r.message == "PROCESSED")
                {
                    clearInterval(refreshIntervalId);
                    $("#finish").removeAttr('disabled');
                    $('#basic_btn').removeClass('hidden');
                    $('#back').removeAttr('disabled');
                    $('#messageBox').addClass('hidden')
                    getRetrieval()

                } else if(min >= 30){
                    clearInterval(refreshIntervalId);
                    $('#basic_btn').removeClass('hidden');
                    $('#back').removeAttr('disabled');
                    $('#messageBox').addClass('hidden')
                }
          })

    }, 20000);
}

function getRetrieval(){
    
    $.ajax({
        url: "/api/method/portal_beneficiario.portal_beneficiario.services.jumio.get_jumio_retrieval",
        dataType: 'json',
        contentType: 'application/json;charset=UTF-8',
    }).done(function(r) {
        sendDynamics();

    });
}

function sendDynamics(){
    $.ajax({
        url: "/api/method/portal_beneficiario.portal_beneficiario.services.dynamics.call_dynamic",
        async: false
      }).done(function(r) {
        console.log("Success");
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

function validatePositiveNumbers(element){
    element.on('keyup', function(){
        var val = this.value;
        this.value = val.replace(/\D|\-/,'');
    });
}


function getCities(value, field, isCity) {
    
    $.ajax({
        url: "/api/method/portal_beneficiario.portal_beneficiario.services.beneficiary.get_cities",
        data: {"code": value, "is_only_city": isCity},
        dataType: 'json',
        async: false
    }).done(function(r) {
        if(r.message){          
            data = r.message;
            
            field.empty();
            field.append("<option></option>");
            
            for (var key in data){
                field.append(`<option value='${data[key].ci_code}'>${data[key].ci_name.toUpperCase()}</option>`);
            }

        } else {
            alert("Sistema en mantenimiento, disculpe las molestias ocasionadas.");
        } 
    });
}