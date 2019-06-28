/* File upload functions */
$('#file_browser').click(function(e){		
	e.preventDefault();		
	$('#file').click();		
});		
$('#file').change(function(){		
	$('#file_path').val($(this).val());
	this.form.submit();
});		
$('#file_path').click(function(){		
	$('#file_browser').click();
});

/* Change between type approval mode and scientific mode */
$(function() {
	$('#tamode').change(function() {
		if ($(this).prop('checked')) {
			$('#simulation-mode').text('Type approval mode');
		} else {
			$('#simulation-mode').text('Scientific mode');
		}
	})
})

/* Advanced options */
function toggle_options() {
	$('#advanced_options').toggle();
}

/* Synchronisation form dynamic fields */
function toggle_wltp_class(el) {
	
	if (el.value == 'WLTP') {
		$('#wltpclass-group').show();
	} else {
		$('#wltpclass-group').hide();
	}
	
}

/* Simulation form advanced options */
$('#chk_only_summary').change(function () {					
	if ($('#chk_only_summary').is(':checked')) {
			$('#only_summary').val('true');
	}   
	else {
			$('#only_summary').val(null);
	}
});

$('#chk_declaration_mode').change(function () {					
	if ($('#chk_declaration_mode').is(':checked')) {
			$('#declaration_mode').val('true');
	}   
	else {
			$('#declaration_mode').val(null);
	}
});	

$('#chk_hard_validation').change(function () {					
	if ($('#chk_hard_validation').is(':checked')) {
			$('#hard_validation').val('true');
	}   
	else {
			$('#hard_validation').val(null);
	}
});

$('#chk_enable_selector').change(function () {					
	if ($('#chk_enable_selector').is(':checked')) {
			$('#enable_selector').val('true');
	}   
	else {
			$('#enable_selector').val(null);
	}
});	

/* Synchronisation form advanced options */
$('#option_reference_data_set').change(function () {					
	$('#reference_data_set').val($('#option_reference_data_set').val());
})

$('#option_x_label').change(function () {					
	$('#x_label').val($('#option_x_label').val());
})

$('#option_y_label').change(function () {					
	$('#y_label').val($('#option_y_label').val());
})

$('#option_interpolation_method').change(function () {					
	$('#interpolation_method').val($('#option_interpolation_method').val());
})

$('#option_header_row_number').change(function () {					
	$('#header_row_number').val($('#option_header_row_number').val());
})


/* Run synchronisation */
function run_synchronisation() {
	$('#synchronise-button').html("<i class=\"fa fa-spin fa-refresh\"></i> Synchronisation in progress...");
	$.ajax({
		url: "/sync/run-synchronisation",
		method: "post",
		data: $('#synchronise-form').serialize(),
		context: document.body
	}).done(function(msg) {
		if (msg == 'OK') {
			$('#logarea').load('/sync/load-log');
			$('#synchronise-button').html("<i class=\"fa fa-refresh\"></i> Synchronise data...");
			$('#synchronise-button').hide();
			$('#file-list').hide();
			$('#file-chooser').hide();
			$('#advanced_options').hide();
			$('#form-container').hide();
			$('#options-link').hide();
			$('#result-toolbar').show();
			$('#sync-result').show();
		} else {
			alert("error");
		}
	});
}

function launch_plot() {
	$('#content-outer').load("/plot/launched", function () { $( window ).resize() })
	$.ajax({
		url: "/plot/model-graph",
		method: "get",
		context: document.body
	})
}