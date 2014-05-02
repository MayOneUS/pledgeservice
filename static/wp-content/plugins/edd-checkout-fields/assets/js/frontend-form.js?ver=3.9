;(function($) {
    var CFM_Form = {
        init: function() {
            // clone and remove repeated field
            $('body').on('click', '#edd_purchase_form_wrap img.cfm-clone-field', this.cloneField);
            $('body').on('click', '#edd_purchase_form_wrap img.cfm-remove-field', this.removeField);

            $('body').on('submit', '#edd_purchase_form', this.formSubmit);
            $('form#post').on('submit', this.adminPostSubmit);
        },

        cloneField: function(e) {
            e.preventDefault();

            var $div = $(this).closest('tr');
            var $clone = $div.clone();
            // console.log($clone);

            //clear the inputs
            $clone.find('input').val('');
            $clone.find(':checked').attr('checked', '');
            $div.after($clone);
        },

        removeField: function() {
            //check if it's the only item
            var $parent = $(this).closest('tr');
            var items = $parent.siblings().andSelf().length;

            if( items > 1 ) {
                $parent.remove();
            }
        },

        adminPostSubmit: function(e) {
            e.preventDefault();

            var form = $(this),
                form_data = CFM_Form.validateForm(form);

            if (form_data) {
                return true;
            }
        },

        formSubmit: function(e) {

            var form = $(this),
                submitButton = form.find('input[type=submit]')
                form_data = CFM_Form.validateForm(form);
			
			if(form_data) {
				return true;
			} else {
				// Prevent the form from submissing is there are errors
	            e.preventDefault();
			}

        },

        validateForm: function( self ) {

            var temp,
                temp_val = '',
                error = false,
                error_items = [];

            // remove all initial errors if any
            CFM_Form.removeErrors(self);
            CFM_Form.removeErrorNotice(self);

            // ===== Validate: Text and Textarea ========
            var required = self.find('[data-required="yes"]');

            required.each(function(i, item) {
                // temp_val = $.trim($(item).val());

                // console.log( $(item).data('type') );
                var data_type = $(item).data('type')
                    val = '';
                    //console.log( data_type );

                switch(data_type) {
                    case 'rich':
                        var name = $(item).data('id')
                        val = $.trim( tinyMCE.get(name).getContent() );

                        if ( val === '') {
                            error = true;

                            // make it warn color
                            CFM_Form.markError(item);
                        }
                        break;

                    case 'textarea':
                    case 'text':
                        val = $.trim( $(item).val() );

                        if ( val === '') {
                            error = true;

                            // make it warn color
                            CFM_Form.markError(item);
                        }
                        break;

                    case 'select':
                        val = $(item).val();

                        // console.log(val);
                        if ( !val || val === '-1' ) {
                            error = true;

                            // make it warn color
                            CFM_Form.markError(item);
                        }
                        break;

                    case 'multiselect':
                        val = $(item).val();

                        if ( val === null || val.length === 0 ) {
                            error = true;

                            // make it warn color
                            CFM_Form.markError(item);
                        }
                        break;

                    case 'checkbox':

                        var length = $(item).parent().find('input:checked').length;

                        if ( ! length ) {
                            error = true;

                            // make it warn color
                            CFM_Form.markError(item);
                        }
                        break;


                    case 'radio':

                        var length = $(item).parent().find('input:checked').length;

                        if ( !length ) {
                            error = true;

                            // make it warn color
                            CFM_Form.markError(item);
                        }
                        break;

                    case 'file':
                        var length = $(item).next('ul').children().length;

                        if ( !length ) {
                            error = true;

                            // make it warn color
                            CFM_Form.markError(item);
                        }
                        break;

                    case 'email':
                        var val = $(item).val();

                        if ( val !== '' ) {
                            //run the validation
                            if( !CFM_Form.isValidEmail( val ) ) {
                                error = true;

                                CFM_Form.markError(item);
                            }
                        }
                        break;


                    case 'url':
                        var val = $(item).val();

                        if ( val !== '' ) {
                            //run the validation
                            if( !CFM_Form.isValidURL( val ) ) {
                                error = true;

                                CFM_Form.markError(item);
                            }
                        }
                        break;

                };

            });

            // if already some error found, bail out
            if (error) {
                // add error notice
                CFM_Form.addErrorNotice(self);
                return false;
            }

            var form_data = self.serialize(),
                rich_texts = [];

            // grab rich texts from tinyMCE
            $('.cfm-rich-validation').each(function (index, item) {
                temp = $(item).data('id');
                val = $.trim( tinyMCE.get(temp).getContent() );

                rich_texts.push(temp + '=' + encodeURIComponent( val ) );
            });

            // append them to the form var
            form_data = form_data + '&' + rich_texts.join('&');
            return form_data;
        },

        addErrorNotice: function(form) {
			$('#edd_purchase_form #edd-purchase-button').attr("disabled", false);
			$('.edd-cart-ajax').hide();
			if( edd_global_vars.complete_purchase )
				$('#edd-purchase-button').val(edd_global_vars.complete_purchase);
			else
				$('#edd-purchase-button').val('Purchase');
			
            $(form).find('#edd_purchase_submit').prepend('<div class="edd_errors"><p class="edd_error">' + cfm_frontend.error_message + '</p></div>');
	   },

        removeErrorNotice: function(form) {
            $(form).find('.cfm-error edd_errors').remove();
        },

        markError: function(item) {
            $(item).closest('fieldset').addClass('has-error');
            $(item).focus();
        },

        removeErrors: function(item) {
            $(item).find('.has-error').removeClass('has-error');
        },

        isValidEmail: function( email ) {
            var pattern = new RegExp(/^((([a-z]|\d|[!#\$%&'\*\+\-\/=\?\^_`{\|}~]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])+(\.([a-z]|\d|[!#\$%&'\*\+\-\/=\?\^_`{\|}~]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])+)*)|((\x22)((((\x20|\x09)*(\x0d\x0a))?(\x20|\x09)+)?(([\x01-\x08\x0b\x0c\x0e-\x1f\x7f]|\x21|[\x23-\x5b]|[\x5d-\x7e]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(\\([\x01-\x09\x0b\x0c\x0d-\x7f]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF]))))*(((\x20|\x09)*(\x0d\x0a))?(\x20|\x09)+)?(\x22)))@((([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])*([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])))\.)+(([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])*([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])))\.?$/i);
            return pattern.test(email);
        },

        isValidURL: function(url) {
            var urlregex = new RegExp("^(http:\/\/www.|https:\/\/www.|ftp:\/\/www.|www.|http:\/\/|https:\/\/){1}([0-9A-Za-z]+\.)");
            return urlregex.test(url);
        },
    };

    $(function() {
        CFM_Form.init();
    });

})(jQuery);