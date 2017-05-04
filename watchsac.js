var API_URL = "http://localhost:8080";

var apiClient = null;

var pages = {};
var NEW_ALERT_PAGE = "new_alert_page";
var NEW_ACCOUNT_SETUP_PAGE = "new_account_setup_page";
var LOGIN_PAGE = "login_page";
var ALERTS_PAGE = "alerts_page";

function deleteAllAlertsFromTable() {
    var alertsTable = document.getElementById('alerts_table');
    var new_tbody = document.createElement('tbody');
    new_tbody.setAttribute('id', 'alerts_table');
    alertsTable.parentNode.replaceChild(new_tbody, alertsTable);
}

function addAlertToTable(id, message, searchTerms) {

    var alertsTable = document.getElementById('alerts_table');

    var newTr = document.createElement('TR');

    var msgTd = document.createElement('TD');
    msgTd.innerHTML = message;
    newTr.appendChild(msgTd);

    var searchTermsTd = document.createElement('TD');
    searchTermsTd.innerHTML = searchTerms.join();
    newTr.appendChild(searchTermsTd);

    var deleteButtonTd = document.createElement('TD');
    deleteButtonTd.innerHTML = '<input class="button" type="button" id="' + id + '" value="Remove" onclick="handleDeleteAlertButtonClick(this.id)">';
    newTr.appendChild(deleteButtonTd);

    alertsTable.appendChild(newTr);
}

function ApiClient(u, p)
{
    // This client provides four methods to interact with the API:
    //      saveNewAccount
    //      getAllAlerts
    //      saveAlert
    //      deleteAlert

    var api_url = API_URL;
    var accounts_ep = "/accounts";
    var alerts_ep = "/alerts";
    var username = u;
    var password = p;

    this.addBasicAuth = function (xhr) {
        xhr.setRequestHeader("Authorization", "Basic " + btoa(username + ":" + password));
    };

    this.saveNewAccount = function(pn, key) {
        var myData = JSON.stringify({
            "u": username,
            "p": password,
            "pn": pn,
            "key": key
        });
        console.log("POST: " + myData);
        $.ajax({
            url: api_url + accounts_ep,
            method: "POST",
            dataType: "json",
            contentType: 'application/json',
            data: myData
        }).done(function(op)  {
            console.log("New account saved successfully.");
        }).fail(
            function(xhr, status, error) {
                console.log("Save failed for some reason...");
                alert('error:' + status + ':' + error + ':' + xhr.responseText);
                alert("A server error occurred saving your new account - please try again.");
                goToPage(NEW_ACCOUNT_SETUP_PAGE);
            }
        );
    };

    this.getAllAlerts = function() {
        $.ajax({
            url: api_url + alerts_ep,
            dataType: "json",
            beforeSend: this.addBasicAuth,
            method: "GET"
        }).done(
            function(data) {
                console.log(data);
                deleteAllAlertsFromTable();
                for (var i=0; i < data.length; i++) {
                    var alert = data[i];
                    addAlertToTable(alert["id"], alert["name"], alert["search_terms"]);
                }
            }
        ).fail(
            function() {
                alert("Failed to load alerts.");
            }
        );
    };

    this.saveAlert = function(alert_json) {
        $.ajax({
            url: api_url + alerts_ep,
            dataType: "json",
            beforeSend: this.addBasicAuth,
            method: "POST",
            data: alert_json,
            contentType: 'application/json'
        }).done(
            function() {
                handleRefreshAlerts();
            }
        ).fail(
            function(data) {
                alert("Save failed.");
            }
        );
    };

    this.deleteAlert = function(alert_id) {
        $.ajax({
            url: api_url + alerts_ep + "?id=" + alert_id,
            beforeSend: this.addBasicAuth,
            method: "DELETE"
        }).done(
            function() {
                handleRefreshAlerts();
            }
        ).fail(
            function(data) {
                alert("Save failed.");
            }
        );
    };
}

function goToPage(page_name)
{
    // After interacting with our API and updating the DOM, all event handlers call into here
    // to navigate to whichever page they're supposed to go to.

    // hide all of the pages
    for (var page in pages) {
        pages[page].hide();
    }
    // show whichever one we're going to
    pages[page_name].show();
}

function areCredentialsFormattedCorrectly(u, p) {
    if (!(typeof u === "string")) {
        console.log('u not a string');
        return false;
    }
    if (!(typeof p === "string")) {
        console.log('p not a string');
        return false;
    }
    if (u.indexOf(':') >= 0 || p.indexOf(':') >= 0) {
        console.log('u or p contain colon');
        return false;
    }
    if (u.length > 25 || p.length > 25) {
        console.log('u or p too long');
        return false;
    }
    if (u.length < 5 || p.length < 5) {
        console.log('u or p too short');
        return false;
    }
    console.log('u and p formatted ok');
    return true;
}

function isPhoneNumberFormattedCorrectly(pn) {
    // +10123456789
    if (!(typeof pn === "string")) {
        console.log('pn not a string');
        return false;
    }
    if (pn.length !== 12) {
        console.log('pn not 12 chars long');
        return false;
    }
    if (pn.charAt(0) !== '+') {
        console.log('first char not a plus sign');
        return false;
    }
    if (pn.charAt(1) !== '1') {
        console.log('second char not a 1');
        return false;
    }
    var nums = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'];
    for (var x=1; x < pn.length; x++) {
        if (!(pn.charAt(x) in nums)) {
            console.log('chars not numbers');
            return false;
        }
    }
    console.log('phone number is formatted ok');
    return true;
}

function isMsgFormattedCorrectly(msg) {
    if (!(typeof msg === "string")) {
        console.log('msg not string');
        return false;
    }
    if (msg.length > 150) {
        console.log('msg too long');
        return false;
    }
    if (msg.length < 2) {
        console.log('msg too short');
        return false;
    }
    console.log('msg is ok');
    return true;
}

function isNewPasswordPairOk(p1, p2) {
    var result = (p1 === p2);
    console.log('pwd is ok?' + result);
    return result;
}

function areSearchTermsFormattedCorrectly(terms) {
    if (!(typeof terms === "string")) {
        return false;
    }
    if (terms.length > 150) {
        return false;
    }
    if (terms.length < 2) {
        return false;
    }
    return true;
}

function buildAlertJson(alertId, name, searchTerms) {
    if (alertId === null) {
        return JSON.stringify({
            "name": name,
            "search_terms": searchTerms.split(",")
        });
    } else {
        return JSON.stringify({
            "id": alertId,
            "name": name,
            "search_terms": searchTerms.split(",")
        });
    }
}

function handleLogIn() {

    console.log('login button was clicked');

    // find the input boxes
    var username_input_box = document.getElementById('username_input');
    var password_input_box = document.getElementById('password_input');

    // pull out the values we need
    var u = username_input_box.value;
    var p = password_input_box.value;

    console.log('Username: ' + u + ', password: ' + p);

    // make sure they're formatted ok
    var credentialsAreFormattedCorrectly = areCredentialsFormattedCorrectly(u, p);

    // clear the input boxes
    username_input_box.value = "";
    password_input_box.value = "";

    // if everything's formatted ok, try to "log in" (fetch the alerts, save credentials, and go to the alerts page)
    if (credentialsAreFormattedCorrectly === true) {
        apiClient = new ApiClient(u, p);
        apiClient.getAllAlerts();
        goToPage(ALERTS_PAGE);
    } else {
        alert("Your username and password were not formatted correctly");
        goToPage(LOGIN_PAGE);
    }
}

function handleSetUpNewAccount() {

    // 1) Validate the inputted information (basic checks on username and password),
    // 2) build a locally-scoped ApiClient with a null username and password (we won't need those fields anyway),
    // 3) use that client to submit the POST request to set up the new account, and
    // 4) navigate the user to the login page

    // find the five input boxes
    var uBox = document.getElementById('new_username_input');
    var pBox = document.getElementById('new_password_input');
    var pBox2 = document.getElementById('new_password_input_2');
    var pnBox = document.getElementById('phone_number_input');
    var keyBox = document.getElementById('new_account_key_input');

    // pull out the four values
    var u = uBox.value;
    var p = pBox.value;
    var pn = pnBox.value;
    var key = keyBox.value;

    // make sure the inputs are ok
    var pwsMatch = isNewPasswordPairOk(p, pBox2.value);
    var credsOk = areCredentialsFormattedCorrectly(u, p);
    var pnOk = isPhoneNumberFormattedCorrectly(pn);

    // clear the input boxes
    uBox.value = '';
    pBox.value = '';
    pBox2.value = '';
    pnBox.value = '';
    keyBox.value = '';

    // if everything is valid, try to set up the new account, then switch the user over to the login page
    if (!(pwsMatch && credsOk && pnOk)) {
        alert("Your new account setup information was not formatted correctly.");
    } else {
        var tempClient = new ApiClient(u, p);
        tempClient.saveNewAccount(pn, key);
        goToPage(LOGIN_PAGE);
    }
}

function handleSaveNewAlert() {

    // find the input boxes
    var msgBox = document.getElementById('alert_message_input');
    var searchTermsBox = document.getElementById('search_terms_input');

    // get their values
    var msg = msgBox.value;
    var terms = searchTermsBox.value;

    // clear the box fields
    msgBox.value = "";
    searchTermsBox.value = "";

    // make sure they're formatted correctly
    if (!(isMsgFormattedCorrectly(msg) && areSearchTermsFormattedCorrectly(terms))) {
        alert("Alert fields are formatted incorrectly.");
    } else {
        var alertJson = buildAlertJson(null, msg, terms);
        console.log("POST: " + alertJson);
        apiClient.saveAlert(alertJson);
    }
}

function handleRefreshAlerts() {
    apiClient.getAllAlerts();
    goToPage(ALERTS_PAGE);
}

function handleSignUpNavClick() {
    goToPage(NEW_ACCOUNT_SETUP_PAGE);
}

function handleNewAlertSetupNavClick() {
    goToPage(NEW_ALERT_PAGE);
}

function handleDeleteAlertButtonClick(alert_id) {
    apiClient.deleteAlert(alert_id);
}

$(document).ready(function() {

    // fill the pages associative array (this is just a convenience)
    pages[NEW_ALERT_PAGE] = $("#" + NEW_ALERT_PAGE);
    pages[ALERTS_PAGE] = $("#" + ALERTS_PAGE);
    pages[LOGIN_PAGE]  = $("#" + LOGIN_PAGE);
    pages[NEW_ACCOUNT_SETUP_PAGE] = $("#" + NEW_ACCOUNT_SETUP_PAGE);

    // register our static button click handlers
    $("#login_submit_button").click(handleLogIn);
    $("#new_account_setup_submit_button").click(handleSetUpNewAccount);
    $("#save_alert_submit_button").click(handleSaveNewAlert);
    $("#refresh_alerts_submit_button").click(handleRefreshAlerts);
    $("#sign_up_nav_button").click(handleSignUpNavClick);
    $("#new_alert_setup_nav_button").click(handleNewAlertSetupNavClick);

    // tell jquery to allow cross-origin requests
    $.support.cors = true
});