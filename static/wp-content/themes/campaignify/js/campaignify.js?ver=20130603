/**
 * Functionality specific to Campaignify.
 *
 * Provides helper functions to enhance the theme experience.
 */

var Campaignify = {}

Campaignify.App = ( function($) {
	function commentForm() {
		$( '#commentform p, .modal-login form p, .modal-register form p' ).each( function(index, value ) {
			var label = $( this ).find( 'label' ),
			    input = $( this ).find( 'input, textarea' );

			label.addClass( 'screen-reader-text' );
			input.attr( 'placeholder', label.text() );
		});
	}

	function campaignWidget() {
		$( '.campaign-widget-embed a' ).attr( 'target', '_blank' );
	}

	return {
		init : function() {
			Campaignify.App.isMobile();
			Campaignify.App.arrowThings();
			Campaignify.App.logInButton();

			commentForm();
			campaignWidget();

			if ( campaignifySettings.page.is_blog || campaignifySettings.campaignWidgets.widget_campaignify_campaign_blog_posts )
				Campaignify.App.gridify();

			$( '.nav-menu-primary .login a, .nav-menu-primary .register a' ).click(function(e) {
				e.preventDefault();
				
				Campaignify.App.fancyBox( $(this), {
					items : {
						src : '#' + $(this).parent().attr( 'id' ) + '-wrap'
					}
				});
			});

			$( '.primary-menu-toggle' ).click(function(e) {
				$( '.site-primary-navigation' ).slideToggle( 'fast' );
			});

			$( '.fancybox' ).click( function(e) {
				e.preventDefault();

				Campaignify.App.fancyBox( $(this ), {
					items : {
						src : $(this).attr( 'href' )
					}
				} );
			} );
		},

		/**
		 * Check if we are on a mobile device (or any size smaller than 980).
		 * Called once initially, and each time the page is resized.
		 */
		isMobile : function( width ) {
			var isMobile = false;

			var width = 1180;
			
			if ( $(window).width() <= width )
				isMobile = true;

			return isMobile;
		},

		fancyBox : function( _this, args ) {
			$.magnificPopup.open( $.extend( args, {
				'type' : 'inline'
			}) );
		},

		arrowThings : function() {
			$.each( $( '.arrowed' ), function() {
				var area  = $(this);
				
				$( '<div class="arrow"></div>' )
					.appendTo( area )
					.css( 'border-top-color', area.css( 'background-color' ) );
			});
		},

		logInButton : function() {
			$( '.nav-menu-primary .login a' )
				.prepend( '<i class="icon-user"></i>' );
		},

		gridify : function() {
			if ( ! $().masonry )
				return;

			var container = $( '.site-content.full' );

			if ( container.masonry() )
				container.masonry( 'reload' );
			
			container.imagesLoaded( function() {
				container.masonry({
					itemSelector : '.hentry',
					columnWidth  : 550,
					gutterWidth  : 40
				});
			});
		}
	}
} )(jQuery);

Campaignify.Widgets = ( function($) {
	function campaignHeroSlider() {
		$( '.campaign-hero-slider-title' ).fitText(1.2);

		var heroSlider = $( '.campaign-hero-slider' ).flexslider({
			controlNav     : false,
			slideshowSpeed : 5000,
			animation      :  'slide',
			prevText       : '<i class="icon-left-open-big"></i>',
			nextText       : '<i class="icon-right-open-big"></i>',
			start          : function(slider) {
				$( '.campaign-hero' ).delay(500).removeClass( 'loading' );
			}
		});
	}

	function campaignBackers() {
		var backerSlider = $( '.campaign-backers-slider' ).flexslider({
			controlNav : false,
			animation  :  'slide',
			prevText   : '<i class="icon-left-open-big"></i>',
			nextText   : '<i class="icon-right-open-big"></i>',
			maxItems   : 6,
			minItems   : 2,
			itemWidth  : 153,
			itemMargin : 44,
			slideshow  : false,
			move       : 2
		});
	}

	function campaignGallery( _this ) {
		var container = _this.parents( '.widget_campaignify_campaign_gallery' ).find( '.campaign-gallery' ),
		    showing   = container.data( 'showing' ),
		    post      = container.data( 'post' );

		var data = {
			'action'  : 'widget_campaignify_campaign_gallery_load',
			'offset'  : showing,
			'post'    : post,
			'_nonce'  : campaignifySettings.security.gallery
		}

		_this.fadeOut();

		$.post( campaignifySettings.ajaxurl, data, function( response ) {
			container.append( response );
		});
	}

	function campaignPledgeLevels() {
		$( '.campaignify-pledge-box' ).click( function(e) {
			e.preventDefault();

			if ( $( this ).hasClass( 'inactive' ) )
				return false;

			var price = $( this ).data( 'price' );

			Campaignify.App.fancyBox( $(this), {
				items : {
					src : '#contribute-modal-wrap'
				},
				callbacks : {
					beforeOpen : function() {
						$( '.edd_price_options' )
							.find( 'li[data-price="' + price + '"]' )
							.trigger( 'click' );
					}
				}
			});
		} );
	}

	return {
		init : function() {
			if ( campaignifySettings.campaignWidgets.widget_campaignify_hero_contribute )
				campaignHeroSlider();

			if ( campaignifySettings.campaignWidgets.widget_campaignify_campaign_backers )
				campaignBackers();

			if ( campaignifySettings.campaignWidgets.widget_campaignify_campaign_gallery ) {
				$( '.campaign-gallery-more' ).click(function(e) {
					e.preventDefault();

					campaignGallery( $(this) );
				});

				$( '.campaign-gallery' ).magnificPopup({
					delegate  : 'a',
					type      : 'image',
					mainClass : 'mfp-img-mobile',
					gallery   : {
						enabled : true,
						navigateByImgClick : true,
						preload : [0,1] // Will preload 0 - before current, and 1 after the current image
					}
				});
			}

			if ( campaignifySettings.campaignWidgets.widget_campaignify_campaign_pledge_levels )
				campaignPledgeLevels();
		},

		resize : function () {
			if ( campaignifySettings.campaignWidgets.widget_campaignify_campaign_pledge_levels )
				campaignPledgeLevels();
		}
	}
} )(jQuery);

Campaignify.Checkout = ( function($) {
	return function() {
		$( '.contribute, .contribute a' ).click(function(e) {
			e.preventDefault();

			Campaignify.App.fancyBox( $(this), {
				items : {
					src : '#contribute-modal-wrap'
				}
			});
		});
	}
} )(jQuery);

jQuery( document ).ready(function($) {
	Campaignify.App.init();
	Campaignify.Widgets.init();

	if ( campaignifySettings.page.is_campaign )
		Campaignify.Checkout();

	$( window ).on( 'resize', function() {
		Campaignify.Widgets.resize();

		Campaignify.App.gridify();
	});
});