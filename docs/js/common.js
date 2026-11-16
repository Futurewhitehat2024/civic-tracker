(function () {
  var config = window.CIVIC || {};
  var name = config.name || "Site";

  function applyBrand() {
    var nodes = document.querySelectorAll("[data-site-name]");
    for (var i = 0; i < nodes.length; i++) {
      nodes[i].textContent = name;
    }
    var page = document.body && document.body.getAttribute("data-page-title");
    document.title = page ? page + " · " + name : name;
  }

  function showMessage(container, text) {
    container.replaceChildren();
    var p = document.createElement("p");
    p.className = "empty";
    p.setAttribute("role", "status");
    p.textContent = text;
    container.appendChild(p);
  }

  function loadFeed(url) {
    return fetch(url, { cache: "no-cache" }).then(function (res) {
      if (!res.ok) {
        throw new Error("HTTP " + res.status);
      }
      return res.json();
    });
  }

  function formatWhen(value) {
    if (!value) {
      return "—";
    }
    var date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return String(value);
    }
    return date.toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  }

  function safeUrl(url) {
    if (!url) {
      return null;
    }
    try {
      var parsed = new URL(url);
      if (parsed.protocol === "http:" || parsed.protocol === "https:") {
        return parsed.href;
      }
    } catch (err) {
      return null;
    }
    return null;
  }

  window.Civic = {
    name: name,
    EMPTY: "No data yet; scrapers not live",
    applyBrand: applyBrand,
    showMessage: showMessage,
    loadFeed: loadFeed,
    formatWhen: formatWhen,
    safeUrl: safeUrl,
  };

  applyBrand();
})();
