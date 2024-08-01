$( document ).ready(function() {

    console.log("aqui");    

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
});