var app = angular.module('delegateApp', []);

app.controller('indexCtrl', function($scope, $http) {
    $scope.accounts = [];
    $scope.lastpayout = 0;
    $scope.nextpayout = 0;

    $http.get ('poollogs.json').then (function (res) {
        $scope.lastpayout = res.data.lastpayout * 1000;
        $scope.nextpayout = moment ($scope.lastpayout).add (1, 'day').valueOf();
        $scope.accounts = [];
	$scope.weight = res.data.weight;
	$scope.riseperday = res.data.riseperday;

        for (addr in res.data.accounts) {
            var it = res.data.accounts[addr];
            it['address'] = addr;
            $scope.accounts.push (it);
        }
    });

    $http.get ('https://wallet.rise.vision/api/delegates/get?username=hybrid_pool').then (function (res) {
        $scope.delegate = res.data.delegate;
    });
});

