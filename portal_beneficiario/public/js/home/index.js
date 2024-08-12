$( document ).ready(function() {
   
    $("form#pb_form").validate({
        rules:{
            phone:'required',
            nationality:'required',
            address:'required',
            city:'required',
            business:'required',
            business_type:'required',
            in:{required: true,digits: true},
            out:{required: true,digits: true},
            assets:{required: true,digits: true},
            passive:{required: true,digits: true},
            source_fund:'required',
            pep:'required'
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
        $('#link_date').datepicker();
    }

    $('#pep').change(function() {
        if(this.checked) {
            $('.pep_fields').removeAttr('hidden');
        }else{
            $('.pep_fields').attr('hidden', true);
        }
    });

    $('#fpep').change(function() {
        if(this.checked) {
            $('.fpep_fields').removeAttr('hidden');
        }else{
            $('.fpep_fields').attr('hidden', true);
        }
    });

    $(".next-step").click(function (e) {
        if($('#pb_form').valid()){
    
            $('#back').prop('disabled', false);
            $('#finish').prop('disabled', false);
            $('#verify_btn').prop('hidden', false);
            $('#messageBox').prop('hidden', true);

            var active = $('.wizard .nav-tabs li.active');
            nextTab(active);

        }else{

            $('#back').prop('disabled', true);
            $('#finish').prop('disabled', true);
            $('#verify_btn').prop('hidden', true);
            $('#messageBox').prop('hidden', false);
        }
        
    });

    $(".prev-step").click(function (e) {
        var active = $('.wizard .nav-tabs li.active');
        prevTab(active);
    });

    $("#finish").click(function (e) {

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
          }).done(function(r) {
            console.log(r.message)
          });
        
    });
});

function nextTab(elem) {
    $(elem).next().find('a[data-toggle="tab"]').click();
}
function prevTab(elem) {
    $(elem).prev().find('a[data-toggle="tab"]').click();
}


$('.nav-tabs').on('click', 'li', function() {
    var li_active = $('.nav-tabs li.active');
    var div_active = li_active.find('a[data-toggle="tab"]').attr('aria-controls');
    $(`#${div_active}`).removeClass('active');
    li_active.removeClass('active');
    $(this).addClass('active');
    var this_div = $(this).find('a[data-toggle="tab"]').attr('aria-controls')
    $(`#${this_div}`).addClass('active');
});