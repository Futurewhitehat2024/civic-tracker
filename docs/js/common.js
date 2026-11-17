(function () {
  var config = window.CIVIC || {};
  var name = config.name || "Site";
  var tagline = config.tagline || "";

  var MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var MONTHS_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

  var KIND_LABELS = {
    bill: "Bill",
    vote: "Vote",
    executive_order: "Executive order",
    federal_register: "Federal Register",
  };

  function applyBrand() {
    var names = document.querySelectorAll("[data-site-name]");
    for (var i = 0; i < names.length; i++) names[i].textContent = name;
    var lines = document.querySelectorAll("[data-site-tagline]");
    for (var j = 0; j < lines.length; j++) lines[j].textContent = tagline;
    var page = document.body && document.body.getAttribute("data-page-title");
    document.title = page ? page + " · " + name : name;
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null && text !== "") node.textContent = text;
    return node;
  }

  function showMessage(container, text) {
    container.replaceChildren();
    var box = el("div", "empty");
    var p = el("p", null, text);
    p.setAttribute("role", "status");
    box.appendChild(p);
    container.appendChild(box);
  }

  function loadFeed(url) {
    return fetch(url, { cache: "no-cache" }).then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    });
  }

  function day(value) {
    if (!value) return "";
    var match = /^(\d{4}-\d{2}-\d{2})/.exec(String(value));
    return match ? match[1] : "";
  }

  function formatDate(value) {
    var iso = day(value);
    if (!iso) return value ? String(value) : "—";
    var parts = iso.split("-");
    return MONTHS_SHORT[Number(parts[1]) - 1] + " " + Number(parts[2]) + ", " + parts[0];
  }

  function formatUpdated(value) {
    var iso = day(value);
    if (!iso) return "Last updated date unavailable";
    var parts = iso.split("-");
    return "Last updated " + MONTHS_LONG[Number(parts[1]) - 1] + " " + Number(parts[2]) + ", " + parts[0];
  }

  function formatWhen(value) {
    return formatDate(value);
  }

  function timeEl(value) {
    var node = el("time", null, formatDate(value));
    var iso = day(value);
    if (iso) node.setAttribute("datetime", iso);
    return node;
  }

  function safeUrl(url) {
    if (!url) return null;
    try {
      var parsed = new URL(url, window.location.href);
      if (parsed.protocol === "http:" || parsed.protocol === "https:") return parsed.href;
    } catch (err) {
      return null;
    }
    return null;
  }

  function officialLink(url, label) {
    var href = safeUrl(url);
    if (!href) return null;
    var link = el("a", "official", label || "Official record");
    link.href = href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.appendChild(el("span", "sr-only", " (opens in a new tab)"));
    return link;
  }

  function chamberLabel(value) {
    if (value === "house") return "House";
    if (value === "senate") return "Senate";
    return value ? String(value) : "";
  }

  function partyLabel(value) {
    var party = String(value || "").trim();
    var low = party.toLowerCase();
    if (!party) return "";
    if (low === "d" || low.indexOf("democrat") === 0) return "Democratic";
    if (low === "r" || low.indexOf("republican") === 0) return "Republican";
    if (low === "i" || low === "independent") return "Independent";
    return party;
  }

  function partyClass(value) {
    var label = partyLabel(value);
    if (label === "Democratic") return "badge badge-d";
    if (label === "Republican") return "badge badge-r";
    if (label === "Independent") return "badge badge-i";
    return "badge";
  }

  function partyMatches(value, filter) {
    if (!filter) return true;
    var party = String(value || "").trim().toLowerCase();
    if (filter === "Democratic") return party === "d" || party === "democratic" || party.indexOf("democrat") === 0;
    if (filter === "Republican") return party === "r" || party === "republican" || party.indexOf("republican") === 0;
    if (filter === "Independent") return party === "i" || party === "independent";
    return party === filter.toLowerCase();
  }

  function kindLabel(value) {
    return KIND_LABELS[value] || (value ? String(value) : "Record");
  }

  function kindClass(value) {
    if (value === "vote") return "badge badge-vote";
    if (value === "executive_order") return "badge badge-order";
    if (value === "bill") return "badge badge-bill";
    if (value === "federal_register") return "badge badge-register";
    return "badge";
  }

  function tradeTypeLabel(value) {
    if (value === "senate-efd-search") return "Disclosure search";
    if (value === "scanned filing") return "Scanned filing";
    if (value === "sale (partial)") return "Partial sale";
    if (!value) return "Transaction";
    return String(value).charAt(0).toUpperCase() + String(value).slice(1);
  }

  function tradeTypeClass(value) {
    if (value === "purchase") return "badge badge-buy";
    if (value === "sale" || value === "sale (partial)") return "badge badge-sell";
    return "badge badge-other";
  }

  function ownerLabel(value) {
    var text = String(value || "").trim();
    if (!text) return "";
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  function noteUpdated(iso) {
    var text = formatUpdated(iso);
    var nodes = document.querySelectorAll("[data-last-updated]");
    for (var i = 0; i < nodes.length; i++) nodes[i].textContent = text;
  }

  function latestStamp(values) {
    var best = null;
    var bestIso = null;
    for (var i = 0; i < values.length; i++) {
      var time = Date.parse(values[i]);
      if (Number.isNaN(time)) continue;
      if (best === null || time > best) {
        best = time;
        bestIso = values[i];
      }
    }
    return bestIso;
  }

  function readParams() {
    return new URLSearchParams(window.location.search);
  }

  function writeParams(map) {
    var params = new URLSearchParams();
    Object.keys(map).forEach(function (key) {
      if (map[key]) params.set(key, map[key]);
    });
    var query = params.toString();
    var next = window.location.pathname + (query ? "?" + query : "");
    var current = window.location.pathname + window.location.search;
    if (next !== current) window.history.replaceState(null, "", next);
  }

  function setOpen(button, nav, open) {
    button.setAttribute("aria-expanded", open ? "true" : "false");
    nav.classList.toggle("is-open", open);
    var label = button.querySelector(".nav-toggle-label");
    if (label) label.textContent = open ? "Close" : "Menu";
  }

  function wireNav() {
    document.documentElement.classList.add("js");
    var button = document.querySelector(".nav-toggle");
    var nav = document.getElementById("site-nav");
    if (!button || !nav) return;
    button.addEventListener("click", function () {
      setOpen(button, nav, button.getAttribute("aria-expanded") !== "true");
    });
    nav.addEventListener("click", function (event) {
      if (event.target.closest("a")) setOpen(button, nav, false);
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && button.getAttribute("aria-expanded") === "true") {
        setOpen(button, nav, false);
        button.focus();
      }
    });
  }

  function wireToc() {
    var links = document.querySelectorAll(".toc a");
    if (!links.length || !("IntersectionObserver" in window)) return;
    var byId = {};
    links.forEach(function (link) {
      var id = (link.getAttribute("href") || "").slice(1);
      if (id) byId[id] = link;
    });
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          links.forEach(function (link) { link.removeAttribute("aria-current"); });
          var current = byId[entry.target.id];
          if (current) current.setAttribute("aria-current", "true");
        });
      },
      { rootMargin: "-20% 0px -65% 0px", threshold: 0.1 }
    );
    Object.keys(byId).forEach(function (id) {
      var section = document.getElementById(id);
      if (section) observer.observe(section);
    });
  }

  function loadSharedUpdated() {
    if (!document.body || !document.body.hasAttribute("data-load-updated")) return;
    Promise.all([
      loadFeed("data/federal.json").catch(function () { return null; }),
      loadFeed("data/trades.json").catch(function () { return null; }),
    ]).then(function (feeds) {
      var stamps = [];
      feeds.forEach(function (feed) {
        if (feed && feed.updated) stamps.push(feed.updated);
      });
      noteUpdated(latestStamp(stamps));
    });
  }

  window.Civic = {
    name: name,
    tagline: tagline,
    EMPTY: "No records are posted yet.",
    applyBrand: applyBrand,
    el: el,
    showMessage: showMessage,
    loadFeed: loadFeed,
    day: day,
    formatWhen: formatWhen,
    formatDate: formatDate,
    formatUpdated: formatUpdated,
    timeEl: timeEl,
    safeUrl: safeUrl,
    officialLink: officialLink,
    chamberLabel: chamberLabel,
    partyLabel: partyLabel,
    partyClass: partyClass,
    partyMatches: partyMatches,
    kindLabel: kindLabel,
    kindClass: kindClass,
    tradeTypeLabel: tradeTypeLabel,
    tradeTypeClass: tradeTypeClass,
    ownerLabel: ownerLabel,
    noteUpdated: noteUpdated,
    latestStamp: latestStamp,
    readParams: readParams,
    writeParams: writeParams,
  };

  applyBrand();
  wireNav();
  wireToc();
  loadSharedUpdated();
})();
