(function () {
  var refresh = document.querySelector("meta[http-equiv='refresh']");
  var home = document.querySelector("a[href='index.html']");
  if (refresh && home) {
    window.location.replace(home.href);
  }
})();
