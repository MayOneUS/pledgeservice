// Part of this function modified from here:
// http://stackoverflow.com/a/2880929/1569632
//
// NOTE: This could be made more efficient by caching the result (and then
// killing the cache on URL changes, but we only call it once, so meh.
var getUrlParams = function() {
  var match,
  pl     = /\+/g,  // Regex for replacing addition symbol with a space
  search = /([^&=]+)=?([^&]*)/g,
  decode = function (s) { return decodeURIComponent(s.replace(pl, " ")); },
  query  = window.location.search.substring(1);

  urlParams = {};
  while (match = search.exec(query))
    urlParams[decode(match[1])] = decode(match[2]);

  return urlParams;
};

var readCookie = function(name) {
  var nameEQ = name + "=";
  var ca = document.cookie.split(';');
  for(var i=0;i < ca.length;i++) {
    var c = ca[i];
    while (c.charAt(0)==' ') c = c.substring(1,c.length);
    if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length,c.length);
  }
  return null;
};

var validateEmail = function(email) {
    var re = /\S+@\S+\.\S+/;
    return re.test(email);
};

var PledgeController = ['$scope', '$http', function($scope, $http) {
  $scope.ctrl = {
    paymentConfig: null,
    stripeHandler: null,

    form: {
      email: '',
      phone: '',
      occupation: '',
      employer: '',
      target: 'Whatever Helps',
      amount: 0,
      unconditional: false,
      subscribe: true
    },
    error: '',
    loading: false,
    cents: function() {
      return Math.floor($scope.ctrl.form.amount * 100);
    },
    validateForm: function() {
      var email = $scope.ctrl.form.email || null;
      var occ = $scope.ctrl.form.occupation || null;
      var emp = $scope.ctrl.form.employer || null;
      
      if (!occ) {
        $scope.ctrl.error = "Please enter occupation";
      } else if (!emp) {
        $scope.ctrl.error = "Please enter employer";
      } else if (!email) {
        $scope.ctrl.error = "Please enter email"; 
      } else if (!validateEmail(email)) {
        $scope.ctrl.error = "Please enter a valid email";
      }
    },
    pledge: function() {
      if ($scope.ctrl.validateForm($scope.ctrl.form)) {
        var cents = $scope.ctrl.cents();
        $scope.ctrl.stripeHandler.open({
          email: $scope.ctrl.form.email,
          amount: cents
        });        
      }
    },
    onTokenRecv: function(token, args) {
      $scope.ctrl.loading = true;
      $scope.ctrl.createPledge(args.billing_name,
                               { STRIPE: { token: token.id } });
    },
    createPledge: function(name, payment) {
      var urlParams = getUrlParams();

      var pledgeType =
            $scope.ctrl.form.unconditional ? 'DONATION' : 'CONDITIONAL';

      $http.post('/r/pledge', {
        email: $scope.ctrl.form.email,
        phone: $scope.ctrl.form.phone,
        name: name,
        occupation: $scope.ctrl.form.occupation,
        employer: $scope.ctrl.form.employer,
        target: $scope.ctrl.form.target,
        subscribe: $scope.ctrl.form.subscribe,
        amountCents: $scope.ctrl.cents(),
        pledgeType: pledgeType,
        team: urlParams['team'] || readCookie("last_team_key") || '',
        payment: payment
      }).success(function(data) {
        location.href = data.receipt_url;
      }).error(function(data) {
        $scope.ctrl.loading = false;

        if ('paymentError' in data) {
          $scope.ctrl.error = "We're having trouble charging your card: " +
            data.paymentError;
        } else {
          $scope.ctrl.error =
            'Oops, something went wrong. Try again in a few minutes';
        }
      });
    }
  };

  $http.get('/r/payment_config').success(function(config) {
    $scope.ctrl.paymentConfig = config;
    $scope.ctrl.stripeHandler = StripeCheckout.configure({
      key: config.stripePublicKey,
      name: 'MayOne.US',
      panelLabel: 'Pledge',
      billingAddress: true,
      image: '/static/flag.jpg',
      token: function(token, args) {
        $scope.ctrl.onTokenRecv(token, args);
      }
    });
  });
}];

angular.module('mayOne',[])
  .controller('PledgeController', PledgeController);
