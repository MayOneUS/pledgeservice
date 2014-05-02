var edd_global_vars;
jQuery(document).ready(function($) {

	Stripe.setPublishableKey( edd_stripe_vars.publishable_key );

		// non ajaxed
		$('body').on('submit', '#edd_purchase_form', function(event) {

			if( $('input[name="edd-gateway"]').val() == 'stripe' ) {

				event.preventDefault();

				edd_stripe_process_card();

			}

		});

});


function edd_stripe_response_handler(status, response) {
	if (response.error) {
		// re-enable the submit button
		jQuery('#edd_purchase_form #edd-purchase-button').attr("disabled", false);

		var error = '<div class="edd_errors"><p class="edd_error">' + response.error.message + '</p></div>';

		// show the errors on the form
		jQuery('#edd-stripe-payment-errors').html(error);

		jQuery('.edd-cart-ajax').hide();
		if( edd_global_vars.complete_purchase )
			jQuery('#edd-purchase-button').val(edd_global_vars.complete_purchase);
		else
			jQuery('#edd-purchase-button').val('Purchase');

	} else {
		var form$ = jQuery("#edd_purchase_form");
		// token contains id, last4, and card type
		var token = response['id'];

		jQuery('#edd_purchase_form #edd_cc_fields input[type="text"]').each(function() {
			jQuery(this).removeAttr('name');
		});

		// insert the token into the form so it gets submitted to the server
		form$.append("<input type='hidden' name='edd_stripe_token' value='" + token + "' />");

		// and submit
		form$.get(0).submit();

	}
}


function edd_stripe_process_card() {

	// disable the submit button to prevent repeated clicks
	jQuery('#edd_purchase_form #edd-purchase-button').attr('disabled', 'disabled');

	if( jQuery('.billing-country').val() ==  'US' ) {
		var state = jQuery('#card_state_us').val();
	} else if( jQuery('.billing-country').val() ==  'CA' ) {
		var state = jQuery('#card_state_ca').val();
	} else {
		var state = jQuery('#card_state_other').val();
	}

	if( typeof jQuery('#card_state_us').val() != 'undefined' ) {

		if( jQuery('.billing-country').val() ==  'US' ) {
			var state = jQuery('#card_state_us').val();
		} else if( jQuery('.billing-country').val() ==  'CA' ) {
			var state = jQuery('#card_state_ca').val();
		} else {
			var state = jQuery('#card_state_other').val();
		}

	} else {
		var state = jQuery('.card_state').val();
	}

	// createToken returns immediately - the supplied callback submits the form if there are no errors
	Stripe.createToken({
		number: 	     jQuery('.card-number').val(),
		name: 		     jQuery('.card-name').val(),
		cvc: 		     jQuery('.card-cvc').val(),
		exp_month:       jQuery('.card-expiry-month').val(),
		exp_year: 	     jQuery('.card-expiry-year').val(),
		address_line1: 	 jQuery('.card-address').val(),
		address_line2: 	 jQuery('.card-address-2').val(),
		address_city: 	 jQuery('.card-city').val(),
		address_state: 	 state,
		address_zip: 	 jQuery('.card-zip').val(),
		address_country: jQuery('#billing_country').val()
	}, edd_stripe_response_handler);

	return false; // submit from callback
}
