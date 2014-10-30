function SubscribeEmail(email) {
    var data = { 
        'email':email,
	'dont_redirect':'true'
    }   
    $.ajax('//pledge.mayday.us/r/subscribe', {data:data, type:'POST'}).done(function() {
    }).fail(function() {
	window.location.replace('https://mayday.us/subscribe/');
    }) 
}

function getUrlParameter(sParam)
{
    var sPageURL = window.location.search.substring(1);
    var sURLVariables = sPageURL.split('&');
    for (var i = 0; i < sURLVariables.length; i++) 
    {
        var sParameterName = sURLVariables[i].split('=');
        if (sParameterName[0] == sParam) 
        {
            return sParameterName[1];
        }
    }
}

function SendEmail() {
    var email = getUrlParameter('email');
    SubscribeEmail(email);     
}
