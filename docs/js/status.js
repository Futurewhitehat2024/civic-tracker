(function () {
  var list = document.querySelector("#feed");
  var meta = document.querySelector("#updated");

  function render(data) {
    var items = data && Array.isArray(data.items) ? data.items : [];
    meta.textContent = data && data.updated
      ? "Updated " + Civic.formatWhen(data.updated)
      : "Not yet updated.";
    Civic.setCount(items.length, items.length, "scraper");
    if (items.length === 0) {
      Civic.showMessage(list, Civic.EMPTY);
      return;
    }

    var table = document.createElement("table");
    var head = document.createElement("thead");
    var headRow = document.createElement("tr");
    ["Scraper", "Last run", "Records", "Errors"].forEach(function (label) {
      var cell = document.createElement("th");
      cell.scope = "col";
      cell.textContent = label;
      headRow.appendChild(cell);
    });
    head.appendChild(headRow);
    table.appendChild(head);

    var body = document.createElement("tbody");
    items.forEach(function (item) {
      var row = document.createElement("tr");
      var name = document.createElement("td");
      name.textContent = item.name || item.id || "Unnamed scraper";
      var lastRun = document.createElement("td");
      lastRun.textContent = item.lastRun ? Civic.formatWhen(item.lastRun) : "Never";
      var records = document.createElement("td");
      records.textContent = typeof item.records === "number" ? String(item.records) : "—";
      var errors = document.createElement("td");
      var messages = Array.isArray(item.errors) ? item.errors.filter(Boolean) : [];
      errors.textContent = messages.length ? messages.join("; ") : "None";
      if (messages.length) {
        errors.className = "has-error";
      }
      row.append(name, lastRun, records, errors);
      body.appendChild(row);
    });
    table.appendChild(body);
    var scroller = document.createElement("div");
    scroller.className = "table-scroll";
    scroller.appendChild(table);
    list.replaceChildren(scroller);
  }

  Civic.loadFeed("data/status.json")
    .then(render)
    .catch(function () {
      meta.textContent = "";
      Civic.setCount(null, null, "scraper");
      Civic.showMessage(list, "Could not load status data.");
    });
})();
