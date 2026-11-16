(function () {
  var list = document.querySelector("#feed");
  var search = document.querySelector("#q");
  var kind = document.querySelector("#kind");
  var meta = document.querySelector("#updated");
  var data = { updated: null, items: [] };

  var kindLabels = {
    bill: "Bill",
    vote: "Vote",
    executive_order: "Executive order",
    federal_register: "Federal Register",
  };

  function matches(item) {
    if (kind.value && item.kind !== kind.value) {
      return false;
    }
    var query = search.value.trim().toLowerCase();
    if (!query) {
      return true;
    }
    var haystack = [item.title, item.summary, item.identifier, item.source, item.id]
      .join(" ")
      .toLowerCase();
    return haystack.indexOf(query) !== -1;
  }

  function render() {
    var items = Array.isArray(data.items) ? data.items : [];
    if (items.length === 0) {
      Civic.showMessage(list, Civic.EMPTY);
      return;
    }
    var shown = items.filter(matches);
    if (shown.length === 0) {
      Civic.showMessage(list, "No items match these filters.");
      return;
    }
    list.replaceChildren();
    shown.forEach(function (item) {
      var article = document.createElement("article");
      article.className = "card";
      var heading = document.createElement("h2");
      var href = Civic.safeUrl(item.url);
      var title = item.title || "Untitled";
      if (href) {
        var link = document.createElement("a");
        link.href = href;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = title;
        heading.appendChild(link);
      } else {
        heading.textContent = title;
      }
      article.appendChild(heading);

      var details = document.createElement("p");
      details.className = "meta";
      details.textContent = [
        kindLabels[item.kind] || item.kind,
        item.identifier,
        item.date,
        item.chamber,
        item.source,
      ]
        .filter(Boolean)
        .join(" · ");
      article.appendChild(details);

      if (item.summary) {
        var summary = document.createElement("p");
        summary.textContent = item.summary;
        article.appendChild(summary);
      }
      list.appendChild(article);
    });
  }

  document.querySelector("#filters").addEventListener("submit", function (event) {
    event.preventDefault();
  });
  search.addEventListener("input", render);
  kind.addEventListener("change", render);

  Civic.loadFeed("data/federal.json")
    .then(function (json) {
      data = json && typeof json === "object" ? json : { items: [] };
      meta.textContent = data.updated
        ? "Updated " + Civic.formatWhen(data.updated)
        : "Not yet updated.";
      render();
    })
    .catch(function () {
      meta.textContent = "";
      Civic.showMessage(list, "Could not load federal data.");
    });
})();
