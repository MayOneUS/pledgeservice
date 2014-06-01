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
      subscribe: true
    },
    error: '',
    loading: false,
    cents: function() {
      return Math.floor($scope.ctrl.form.amount * 100);
    },
    pledge: function() {
      var cents = $scope.ctrl.cents();
      $scope.ctrl.stripeHandler.open({
        email: $scope.ctrl.form.email,
        amount: cents
      });
    },
    onTokenRecv: function(token, args) {
      $scope.ctrl.loading = true;
      $scope.ctrl.createPledge(args.billing_name,
                               { STRIPE: { token: token.id } });
    },
    createPledge: function(name, payment) {
      var urlParams = getUrlParams();

      $http.post('/r/pledge', {
        email: $scope.ctrl.form.email,
        phone: $scope.ctrl.form.phone,
        name: name,
        occupation: $scope.ctrl.form.occupation,
        employer: $scope.ctrl.form.employer,
        target: $scope.ctrl.form.target,
        subscribe: $scope.ctrl.form.subscribe,
        amountCents: $scope.ctrl.cents(),
        pledgeType: 'CONDITIONAL',
        team: urlParams['team'] || '',
        payment: payment
      }).success(function(data) {
        location.href = data.receipt_url;
      }).error(function() {
        $scope.ctrl.loading = false;
        $scope.ctrl.error =
          'Oops, something went wrong. Try again in a few minutes';
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
