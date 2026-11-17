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
    var hash = window.location.hash || "";
    var next = window.location.pathname + (query ? "?" + query : "") + hash;
    var current = window.location.pathname + window.location.search + hash;
    if (next !== current) window.history.replaceState(null, "", next);
  }

  function fileName() {
    var file = "";
    try {
      file = decodeURIComponent(window.location.pathname.split("/").pop() || "");
    } catch (err) {
      file = window.location.pathname.split("/").pop() || "";
    }
    if (!file) return "index.html";
    return file.toLowerCase();
  }

  function crumbLink(href, label) {
    return { href: href, label: label };
  }

  function federalPlace(kind, chamber) {
    var names = {
      bill: ["bills", "Bills"],
      executive_order: ["orders", "Executive orders"],
      federal_register: ["register", "Federal Register"],
    };
    if (kind === "vote" && (chamber === "house" || chamber === "senate")) {
      var which = chamber === "house" ? "House" : "Senate";
      return {
        key: "votes-" + chamber,
        section: "votes",
        doc: which + " votes",
        kicker: "Votes",
        title: which + " votes",
        crumbs: [crumbLink("federal.html", "Federal actions"), crumbLink("federal.html?kind=vote", "Votes"), which],
      };
    }
    if (kind === "vote") {
      return {
        key: "votes",
        section: "votes",
        doc: "Votes",
        kicker: "Federal actions",
        title: "Votes",
        crumbs: [crumbLink("federal.html", "Federal actions"), "Votes"],
      };
    }
    if (names[kind]) {
      return {
        key: names[kind][0],
        section: "federal",
        doc: names[kind][1],
        kicker: "Federal actions",
        title: names[kind][1],
        crumbs: [crumbLink("federal.html", "Federal actions"), names[kind][1]],
      };
    }
    return { key: "federal", section: "federal", doc: "Federal actions", crumbs: ["Federal actions"] };
  }

  function tradePlace(chamber, party, hash) {
    var parties = {
      Democratic: ["officials-d", "Democratic members"],
      Republican: ["officials-r", "Republican members"],
      Independent: ["officials-i", "Independent members"],
    };
    var chambers = { house: "House", senate: "Senate" };
    var partyInfo = parties[party];
    var chamberLabel = chambers[chamber];
    var officials = !!partyInfo || hash === "#officials";
    if (officials && partyInfo && chamberLabel) {
      return {
        key: partyInfo[0],
        section: "officials",
        doc: partyInfo[1],
        kicker: "Officials",
        title: partyInfo[1],
        crumbs: [
          crumbLink("trades.html#officials", "Officials"),
          crumbLink("trades.html?chamber=" + chamber + "#officials", chamberLabel + " members"),
          partyInfo[1],
        ],
        also: ["trades-" + chamber],
      };
    }
    if (officials && partyInfo) {
      return {
        key: partyInfo[0],
        section: "officials",
        doc: partyInfo[1],
        kicker: "Officials",
        title: partyInfo[1],
        crumbs: [crumbLink("trades.html#officials", "Officials"), partyInfo[1]],
      };
    }
    if (officials && chamberLabel) {
      return {
        key: "officials-" + chamber,
        section: "officials",
        doc: chamberLabel + " members",
        kicker: "Officials",
        title: chamberLabel + " members",
        crumbs: [crumbLink("trades.html#officials", "Officials"), chamberLabel + " members"],
        also: ["trades-" + chamber],
      };
    }
    if (officials) {
      return {
        key: "officials",
        section: "officials",
        doc: "Officials",
        kicker: "Officials",
        title: "Officials",
        crumbs: ["Officials"],
      };
    }
    if (chamberLabel) {
      return {
        key: "trades-" + chamber,
        section: "trades",
        doc: chamberLabel + " disclosures",
        kicker: "Trades and disclosures",
        title: chamberLabel + " disclosures",
        crumbs: [crumbLink("trades.html", "Trades and disclosures"), chamberLabel],
      };
    }
    return { key: "trades", section: "trades", doc: "Congressional trades", crumbs: ["Trades and disclosures"] };
  }

  function aboutPlace(hash) {
    var sections = {
      purpose: "Purpose",
      sources: "Sources",
      records: "What you will find",
      schedule: "Update schedule",
      reading: "How to read a disclosure",
      disclaimer: "Disclaimer",
    };
    var id = (hash || "").replace(/^#/, "");
    if (sections[id]) {
      return {
        key: "about-" + id,
        section: "about",
        doc: sections[id],
        crumbs: [crumbLink("about.html", "About"), sections[id]],
      };
    }
    return { key: "about", section: "about", doc: "About", crumbs: ["About"] };
  }

  function currentPlace() {
    var file = fileName();
    var params = new URLSearchParams(window.location.search);
    var kind = params.get("kind") || "";
    var chamber = params.get("chamber") || "";
    if (chamber !== "house" && chamber !== "senate") chamber = "";
    var party = params.get("party") || "";
    if (!Object.prototype.hasOwnProperty.call({ Democratic: 1, Republican: 1, Independent: 1 }, party)) party = "";
    var hash = window.location.hash || "";
    if (file === "index.html") return { key: "home", section: "", doc: "Home" };
    if (file === "about.html") return aboutPlace(hash);
    if (file === "trades.html") return tradePlace(chamber, party, hash);
    if (file === "federal.html") return federalPlace(kind, chamber);
    return { key: "", section: "", doc: "" };
  }

  function fillCrumbs(crumbs) {
    var nav = document.querySelector(".crumbs");
    if (!nav || !crumbs) return;
    var list = nav.querySelector("ol");
    if (!list) return;
    list.replaceChildren();
    var homeItem = document.createElement("li");
    var homeLink = document.createElement("a");
    homeLink.href = "index.html";
    homeLink.textContent = "Home";
    homeItem.appendChild(homeLink);
    list.appendChild(homeItem);
    crumbs.forEach(function (crumb, index) {
      var item = document.createElement("li");
      var last = index === crumbs.length - 1;
      var label = typeof crumb === "string" ? crumb : crumb.label;
      if (!last && crumb && crumb.href) {
        var link = document.createElement("a");
        link.href = crumb.href;
        link.textContent = label;
        item.appendChild(link);
      } else {
        item.textContent = label;
        if (last) item.setAttribute("aria-current", "page");
      }
      list.appendChild(item);
    });
  }

  function paintPlace() {
    var place = currentPlace();
    var marked = document.querySelectorAll("#site-nav [aria-current], .section-nav [aria-current], .footer-map [aria-current]");
    for (var i = 0; i < marked.length; i++) marked[i].removeAttribute("aria-current");
    if (place.key) {
      var hits = document.querySelectorAll('[data-nav="' + place.key + '"]');
      for (var h = 0; h < hits.length; h++) hits[h].setAttribute("aria-current", "page");
    }
    if (place.section) {
      var summaries = document.querySelectorAll('.nav-item[data-nav-section="' + place.section + '"] > .nav-parent');
      for (var s = 0; s < summaries.length; s++) summaries[s].setAttribute("aria-current", "true");
    }
    if (place.also) {
      place.also.forEach(function (navKey) {
        var extras = document.querySelectorAll('.section-nav [data-nav="' + navKey + '"]');
        for (var e = 0; e < extras.length; e++) extras[e].setAttribute("aria-current", "page");
      });
    }
    var heading = document.querySelector(".page-head h1");
    var kicker = document.querySelector(".page-head .kicker");
    if (heading) heading.textContent = place.title || heading.getAttribute("data-base-title") || heading.textContent;
    if (kicker) kicker.textContent = place.kicker || kicker.getAttribute("data-base-kicker") || kicker.textContent;
    if (place.crumbs) fillCrumbs(place.crumbs);
    if (place.doc && document.body) {
      document.body.setAttribute("data-page-title", place.doc);
      applyBrand();
    }
  }

  function closeMenus(except) {
    var items = document.querySelectorAll("#site-nav .nav-item");
    for (var i = 0; i < items.length; i++) {
      if (items[i] !== except) items[i].open = false;
    }
  }

  function topLevel(nav) {
    var nodes = [];
    var children = nav.children;
    for (var i = 0; i < children.length; i++) {
      var child = children[i];
      if (child.matches("a.nav-link")) nodes.push(child);
      else if (child.classList.contains("nav-item")) {
        var summary = child.querySelector(".nav-parent");
        if (summary) nodes.push(summary);
      }
    }
    return nodes;
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
    if (!nav) return;

    if (button) {
      button.addEventListener("click", function () {
        var open = button.getAttribute("aria-expanded") === "true";
        if (open) closeMenus(null);
        setOpen(button, nav, !open);
      });
    }

    nav.addEventListener("toggle", function (event) {
      var item = event.target;
      if (!item.classList || !item.classList.contains("nav-item") || !item.open) return;
      closeMenus(item);
    }, true);

    nav.addEventListener("click", function (event) {
      if (!event.target.closest("a") || !button) return;
      closeMenus(null);
      setOpen(button, nav, false);
    });

    nav.addEventListener("keydown", function (event) {
      var key = event.key;
      var tops = topLevel(nav);
      var summary = event.target.closest(".nav-parent");
      var menuLink = event.target.closest(".nav-menu a");
      var homeLink = event.target.closest("a.nav-link");

      if (summary && tops.indexOf(summary) !== -1) {
        var index = tops.indexOf(summary);
        var item = summary.parentNode;
        if (key === "ArrowDown" || key === "ArrowUp") {
          event.preventDefault();
          item.open = true;
          var links = item.querySelectorAll(".nav-menu a");
          if (!links.length) return;
          (key === "ArrowDown" ? links[0] : links[links.length - 1]).focus();
        } else if (key === "ArrowRight" || key === "ArrowLeft") {
          event.preventDefault();
          closeMenus(null);
          var next = key === "ArrowRight" ? (index + 1) % tops.length : (index - 1 + tops.length) % tops.length;
          tops[next].focus();
        } else if (key === "Home" || key === "End") {
          event.preventDefault();
          tops[key === "Home" ? 0 : tops.length - 1].focus();
        } else if (key === "Escape" && item.open) {
          event.preventDefault();
          event.stopPropagation();
          item.open = false;
        }
        return;
      }

      if (menuLink) {
        var menuLinks = Array.prototype.slice.call(menuLink.closest(".nav-menu").querySelectorAll("a"));
        var linkIndex = menuLinks.indexOf(menuLink);
        var parentItem = menuLink.closest(".nav-item");
        var parentSummary = parentItem.querySelector(".nav-parent");
        if (key === "ArrowDown" || key === "ArrowUp") {
          event.preventDefault();
          if (key === "ArrowUp" && linkIndex <= 0) parentSummary.focus();
          else menuLinks[(linkIndex + (key === "ArrowDown" ? 1 : -1) + menuLinks.length) % menuLinks.length].focus();
        } else if (key === "Home" || key === "End") {
          event.preventDefault();
          menuLinks[key === "Home" ? 0 : menuLinks.length - 1].focus();
        } else if (key === "Escape") {
          event.preventDefault();
          event.stopPropagation();
          parentItem.open = false;
          parentSummary.focus();
        }
        return;
      }

      if (homeLink && tops.indexOf(homeLink) !== -1) {
        var homeIndex = tops.indexOf(homeLink);
        if (key === "ArrowRight" || key === "ArrowLeft") {
          event.preventDefault();
          closeMenus(null);
          var step = key === "ArrowRight" ? (homeIndex + 1) % tops.length : (homeIndex - 1 + tops.length) % tops.length;
          tops[step].focus();
        } else if (key === "Home" || key === "End") {
          event.preventDefault();
          tops[key === "Home" ? 0 : tops.length - 1].focus();
        }
      }
    });

    var items = nav.querySelectorAll(".nav-item");
    for (var i = 0; i < items.length; i++) {
      items[i].addEventListener("focusout", function (event) {
        var item = event.currentTarget;
        var next = event.relatedTarget;
        if (!next || item.contains(next)) return;
        item.open = false;
      });
    }

    document.addEventListener("click", function (event) {
      var header = document.querySelector(".masthead");
      if (!header || header.contains(event.target)) return;
      closeMenus(null);
      if (button && button.getAttribute("aria-expanded") === "true") setOpen(button, nav, false);
    });

    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape") return;
      var openItem = nav.querySelector(".nav-item[open]");
      if (openItem) {
        var summary = openItem.querySelector(".nav-parent");
        openItem.open = false;
        if (summary) summary.focus();
        return;
      }
      if (button && button.getAttribute("aria-expanded") === "true") {
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

  function syncAfterFilters() {
    if (window.location.hash === "#officials") {
      var params = new URLSearchParams(window.location.search);
      var leftover = params.get("chamber") || params.get("party") || params.get("q") || params.get("type") || params.get("owner") || params.get("from") || params.get("to") || params.get("source") || params.get("kind");
      if (!leftover) window.history.replaceState(null, "", window.location.pathname + window.location.search);
    }
    paintPlace();
  }

  var filters = document.getElementById("filters");
  if (filters) filters.addEventListener("change", paintPlace);
  document.addEventListener("click", function (event) {
    if (!event.target.closest || !event.target.closest("#clear")) return;
    window.setTimeout(syncAfterFilters, 0);
  });
  window.addEventListener("hashchange", paintPlace);
  window.addEventListener("popstate", paintPlace);

  applyBrand();
  wireNav();
  wireToc();
  loadSharedUpdated();
  paintPlace();
})();
