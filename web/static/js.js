function send(item, state) {
  var xmlhttp = new XMLHttpRequest();
  xmlhttp.open("POST","/nexa/" + item + "/" + state);
  xmlhttp.send();
}

function saveConfig() {
  var config = document.getElementById('configArea').value,
      xmlhttp = new XMLHttpRequest();
  xmlhttp.open("POST","/config");
  xmlhttp.send(config);
}
