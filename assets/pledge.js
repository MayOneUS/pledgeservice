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
      $http.post('/r/pledge', {
        email: $scope.ctrl.form.email,
        phone: $scope.ctrl.form.phone,
        name: name,
        occupation: $scope.ctrl.form.occupation,
        employer: $scope.ctrl.form.employer,
        target: $scope.ctrl.form.target,
        subscribe: $scope.ctrl.form.subscribe,
        amountCents: $scope.ctrl.cents(),
        team: '',
        payment: payment
      }).success(function(data) {
        location.href = data.receipt_url;
      }).error(function() {
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
