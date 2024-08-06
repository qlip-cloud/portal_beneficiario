$( document ).ready(function() {
   

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
    
    //Wizard
    $('a[data-toggle="tab"]').on('shown.bs.tab', function (e) {

        var target = $(e.target);
    
        if (target.parent().hasClass('disabled')) {
            return false;
        }
    });

    $(".next-step").click(function (e) {

        var active = $('.wizard .nav-tabs li.active');
        active.next().removeClass('disabled');
        nextTab(active);

    });
    $(".prev-step").click(function (e) {

        var active = $('.wizard .nav-tabs li.active');
        prevTab(active);

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