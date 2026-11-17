(function () {
  var header = document.querySelector(".site-header");
  var toggle = document.querySelector(".nav-toggle");
  var nav = document.querySelector("#site-nav");
  if (!header || !toggle || !nav) {
    return;
  }

  var desktop = window.matchMedia("(min-width: 700px)");

  function setOpen(open) {
    header.classList.toggle("is-open", open);
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
  }

  toggle.addEventListener("click", function () {
    setOpen(toggle.getAttribute("aria-expanded") !== "true");
  });

  nav.addEventListener("click", function (event) {
    if (event.target.closest("a")) {
      setOpen(false);
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      setOpen(false);
    }
  });

  document.addEventListener("click", function (event) {
    if (!header.classList.contains("is-open")) {
      return;
    }
    if (!header.contains(event.target)) {
      setOpen(false);
    }
  });

  function closeIfDesktop() {
    if (desktop.matches) {
      setOpen(false);
    }
  }

  if (desktop.addEventListener) {
    desktop.addEventListener("change", closeIfDesktop);
  } else if (desktop.addListener) {
    desktop.addListener(closeIfDesktop);
  }
})();
