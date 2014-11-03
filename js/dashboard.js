// initializes Bootstrap Validator plugin and other event handlers
$(document).ready(function() {
	$("#edit_user_submit").click(function() {
		update_user();
		// Return false to disable ACTUAL submit
		// Note that we are using a submit button so that bootstrapValidator will disable
		// it if invalid.  May try to alter that in the future
		return false;
	});

	$("#verify_user_button").click(function() {
		$("#verify_user_modal").modal();
	});

	$("#verify_user_submit").click(function() {
		verify_user();
		return false;
	});

	$("#edit_user_modal").on("hidden.bs.modal", function() {
		// TODO: Doesn't work for absolutely no reason.  Does it's purpose in the console no problem.
		$("#edit_user_form").bootstrapValidator('resetForm', true);

		var uname = $("#name").text();
		var phone = $("#phone_number").text();

		$("#edit_user_name").val(uname);
		$("#edit_user_phone").val(phone);
	});

	$("#edit_user_button").click(function() {
		$("#edit_user_modal").modal();
	});

	$('#edit_user_form').bootstrapValidator({
		feedbackIcons: {
			valid: 'glyphicon glyphicon-ok',
			invalid: 'glyphicon glyphicon-remove',
			validating: 'glyphicon glyphicon-refresh'
		},
		submitButtons: 'button[type="submit"]',
		fields: {
			edit_user_name: {
				validators: {
					notEmpty: {
						message: "Please enter your name."
					}
				}
			},
			edit_user_phone: {
				validators: {
					notEmpty: {
						message: "Please enter your phone number."
					},
					phone: {
						message: "Please enter a valid phone number.",
						country: "US"
					}
				}
			}
		}
	});
});

function update_user() {
	var name = $("#edit_user_name").val();
	var phone = $("#edit_user_phone").val();

	$("#edit_user_modal").modal('hide');

	var post_data = {
		'name': name,
		'phone_number': phone
	};

	$.post("/customer/dash/edit", post_data, function(data) {
		$("#name").text(name);
		$("#phone_number").text(phone);

		if(data.updated_phone) {
			$("#verified").removeClass("glyphicon-ok").addClass("glyphicon-remove");
			$("#verify_user_button").show();
		}
	});
}

function verify_user() {
	$("#verify_user_modal").modal('hide');

	var verification_code = $("#verify_user_verification_code").val();
	var post_data = {
		'verification_code': verification_code
	};

	$.post("/customer/dash/verify", post_data, function(data) {
		if(data.verified) {
			$("#verified").addClass("glyphicon-ok").removeClass("glyphicon-remove");
			$("#verify_user_button").hide();
			// Display message
		} else {
			// Display failure message
		}
	});
}

