(function () {
  var list = document.querySelector("#feed");
  var form = document.querySelector("#filters");
  var search = document.querySelector("#q");
  var kind = document.querySelector("#kind");
  var source = document.querySelector("#source");
  var chamber = document.querySelector("#chamber");
  var fromInput = document.querySelector("#from");
  var toInput = document.querySelector("#to");
  var sortSelect = document.querySelector("#sort");
  var countEl = document.querySelector("#count");
  var clearBtn = document.querySelector("#clear");
  var data = { updated: null, items: [] };
  var sortState = { key: "date", dir: "desc" };

  function items() {
    return Array.isArray(data.items) ? data.items : [];
  }

  function matches(item) {
    if (kind.value && item.kind !== kind.value) return false;
    if (source.value && item.source !== source.value) return false;
    if (chamber.value === "none" && item.chamber) return false;
    if (chamber.value && chamber.value !== "none" && item.chamber !== chamber.value) return false;
    var when = Civic.day(item.date);
    if (fromInput.value && (!when || when < fromInput.value)) return false;
    if (toInput.value && (!when || when > toInput.value)) return false;
    var query = search.value.trim().toLowerCase();
    if (!query) return true;
    var haystack = [item.title, item.summary, item.identifier, item.source, item.id, Civic.kindLabel(item.kind)]
      .join(" ")
      .toLowerCase();
    return haystack.indexOf(query) !== -1;
  }

  function valueFor(item, key) {
    if (key === "date") return Civic.day(item.date);
    if (key === "title") return String(item.title || "").toLowerCase();
    if (key === "kind") return Civic.kindLabel(item.kind).toLowerCase();
    if (key === "identifier") return String(item.identifier || "").toLowerCase();
    if (key === "chamber") return Civic.chamberLabel(item.chamber).toLowerCase();
    if (key === "source") return String(item.source || "").toLowerCase();
    return "";
  }

  function sortItems(rows) {
    var dir = sortState.dir === "asc" ? 1 : -1;
    return rows.slice().sort(function (a, b) {
      var left = valueFor(a, sortState.key);
      var right = valueFor(b, sortState.key);
      if (left < right) return -1 * dir;
      if (left > right) return 1 * dir;
      var ida = String(a.id || "");
      var idb = String(b.id || "");
      if (ida < idb) return -1;
      if (ida > idb) return 1;
      return 0;
    });
  }

  function syncSortSelect() {
    var value = sortState.key + "-" + sortState.dir;
    if (sortSelect.querySelector('option[value="' + value + '"]')) sortSelect.value = value;
  }

  function writeQuery() {
    Civic.writeParams({
      q: search.value.trim(),
      kind: kind.value,
      source: source.value,
      chamber: chamber.value,
      from: fromInput.value,
      to: toInput.value,
      sort: sortSelect.value !== "date-desc" ? sortSelect.value : "",
    });
  }

  function setCount(shown, total) {
    var noun = shown === 1 ? "federal action" : "federal actions";
    countEl.textContent = shown === total
      ? "Showing " + shown.toLocaleString() + " " + noun + "."
      : "Showing " + shown.toLocaleString() + " of " + total.toLocaleString() + " federal actions.";
  }

  function summaryBlock(text) {
    var wrap = Civic.el("div", "summary-block");
    var paragraph = Civic.el("p", "summary");
    var long = text.length > 240;
    var clipped = text.slice(0, 240).replace(/\s+\S*$/, "") + "…";
    paragraph.textContent = long ? clipped : text;
    wrap.appendChild(paragraph);
    if (long) {
      var button = Civic.el("button", "text-button", "Show full summary");
      button.type = "button";
      button.setAttribute("aria-expanded", "false");
      button.addEventListener("click", function () {
        var open = button.getAttribute("aria-expanded") === "true";
        button.setAttribute("aria-expanded", open ? "false" : "true");
        button.textContent = open ? "Show full summary" : "Hide full summary";
        paragraph.textContent = open ? clipped : text;
      });
      wrap.appendChild(button);
    }
    return wrap;
  }

  function headerCell(label, key) {
    var cell = Civic.el("th");
    cell.scope = "col";
    if (sortState.key === key) cell.setAttribute("aria-sort", sortState.dir === "asc" ? "ascending" : "descending");
    else cell.setAttribute("aria-sort", "none");
    var button = Civic.el("button", null, label);
    button.type = "button";
    button.setAttribute("data-sort", key);
    var mark = Civic.el("span", "sort-ind", sortState.key === key ? (sortState.dir === "asc" ? "↑" : "↓") : "");
    mark.setAttribute("aria-hidden", "true");
    button.appendChild(mark);
    cell.appendChild(button);
    return cell;
  }

  function render() {
    var rows = items();
    if (rows.length === 0) {
      countEl.textContent = "No federal actions are posted yet.";
      Civic.showMessage(list, "No federal actions are posted yet. Check back after the next daily update.");
      writeQuery();
      return;
    }
    var shown = sortItems(rows.filter(matches));
    setCount(shown.length, rows.length);
    if (shown.length === 0) {
      list.replaceChildren();
      var box = Civic.el("div", "empty");
      var message = Civic.el("p", null, "No federal actions match these filters. Try a broader search, a different type, or a wider date range.");
      message.setAttribute("role", "status");
      var button = Civic.el("button", "text-button", "Clear filters");
      button.type = "button";
      button.addEventListener("click", resetFilters);
      box.append(message, button);
      list.appendChild(box);
      writeQuery();
      return;
    }

    var table = Civic.el("table", "data-table");
    var caption = Civic.el("caption", "sr-only", countEl.textContent + " Sorted by " + sortState.key + ", " + sortState.dir + ".");
    table.appendChild(caption);
    var head = Civic.el("thead");
    var headRow = Civic.el("tr");
    [
      ["Date", "date"],
      ["Type", "kind"],
      ["Action", "title"],
      ["Number", "identifier"],
      ["Chamber", "chamber"],
      ["Source", "source"],
    ].forEach(function (pair) {
      headRow.appendChild(headerCell(pair[0], pair[1]));
    });
    head.appendChild(headRow);
    table.appendChild(head);

    var body = Civic.el("tbody");
    shown.forEach(function (item) {
      var row = Civic.el("tr");

      var dateCell = Civic.el("td");
      dateCell.appendChild(Civic.timeEl(item.date));
      row.appendChild(dateCell);

      var typeCell = Civic.el("td");
      typeCell.appendChild(Civic.el("span", Civic.kindClass(item.kind), Civic.kindLabel(item.kind)));
      row.appendChild(typeCell);

      var actionCell = Civic.el("td", "action-cell");
      var title = item.title || "Untitled action";
      var link = Civic.officialLink(item.url, title);
      if (link) {
        link.classList.add("title-link");
        actionCell.appendChild(link);
      } else {
        actionCell.appendChild(Civic.el("span", "title-link", title));
      }
      if (item.summary) actionCell.appendChild(summaryBlock(String(item.summary)));
      row.appendChild(actionCell);

      row.appendChild(Civic.el("td", "nowrap", item.identifier || "—"));

      var chamberCell = Civic.el("td", null, Civic.chamberLabel(item.chamber) || "—");
      row.appendChild(chamberCell);

      var sourceCell = Civic.el("td");
      if (item.source) sourceCell.appendChild(Civic.el("span", "source-name", item.source));
      else sourceCell.textContent = "—";
      var record = Civic.officialLink(item.url, "View record");
      if (record) sourceCell.appendChild(record);
      row.appendChild(sourceCell);

      body.appendChild(row);
    });
    table.appendChild(body);

    var scroller = Civic.el("div", "table-scroll");
    scroller.tabIndex = 0;
    scroller.setAttribute("role", "region");
    scroller.setAttribute("aria-label", "Federal actions table");
    scroller.appendChild(table);
    list.replaceChildren(scroller);
    writeQuery();
  }

  function fillSources(rows) {
    var names = [];
    rows.forEach(function (item) {
      if (item.source && names.indexOf(item.source) === -1) names.push(item.source);
    });
    names.sort();
    names.forEach(function (label) {
      var option = Civic.el("option", null, label);
      option.value = label;
      source.appendChild(option);
    });
  }

  function applySortValue(value) {
    var parts = String(value || "date-desc").split("-");
    var dir = parts.pop();
    var key = parts.join("-");
    if (dir !== "asc" && dir !== "desc") return;
    sortState.key = key || "date";
    sortState.dir = dir;
  }

  function hasOption(select, value) {
    for (var i = 0; i < select.options.length; i++) {
      if (select.options[i].value === value) return true;
    }
    return false;
  }

  function readQuery() {
    var params = Civic.readParams();
    if (params.get("q")) search.value = params.get("q");
    if (params.get("kind") && hasOption(kind, params.get("kind"))) kind.value = params.get("kind");
    if (params.get("source") && hasOption(source, params.get("source"))) source.value = params.get("source");
    if (params.get("chamber") && hasOption(chamber, params.get("chamber"))) chamber.value = params.get("chamber");
    if (params.get("from")) fromInput.value = params.get("from");
    if (params.get("to")) toInput.value = params.get("to");
    if (params.get("sort") && hasOption(sortSelect, params.get("sort"))) {
      sortSelect.value = params.get("sort");
      applySortValue(params.get("sort"));
    }
  }

  function resetFilters() {
    form.reset();
    sortState = { key: "date", dir: "desc" };
    sortSelect.value = "date-desc";
    render();
  }

  form.addEventListener("submit", function (event) { event.preventDefault(); });
  [search, kind, source, chamber, fromInput, toInput].forEach(function (input) {
    input.addEventListener("input", render);
    input.addEventListener("change", render);
  });
  sortSelect.addEventListener("change", function () {
    applySortValue(sortSelect.value);
    render();
  });
  clearBtn.addEventListener("click", resetFilters);
  list.addEventListener("click", function (event) {
    var button = event.target.closest("button[data-sort]");
    if (!button) return;
    var key = button.getAttribute("data-sort");
    if (sortState.key === key) sortState.dir = sortState.dir === "asc" ? "desc" : "asc";
    else {
      sortState.key = key;
      sortState.dir = key === "date" ? "desc" : "asc";
    }
    syncSortSelect();
    render();
  });

  Civic.loadFeed("data/federal.json")
    .then(function (json) {
      data = json && typeof json === "object" ? json : { items: [] };
      Civic.noteUpdated(data.updated);
      fillSources(items());
      readQuery();
      render();
    })
    .catch(function () {
      countEl.textContent = "";
      Civic.noteUpdated(null);
      Civic.showMessage(list, "Federal actions could not be loaded. Refresh the page to try again.");
    });
})();
