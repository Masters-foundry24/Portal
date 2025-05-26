

let account_id = document.getElementById("paid_to_id");
let account_name = document.getElementById("paid_to_name");

account_id.addEventListener("blur", function(event) {
    fetch(`/get_account_name?account_id=${encodeURIComponent(account_id.value)}`).then(res => res.json()).then(data => {account_name.textContent = data.account_name});
})
