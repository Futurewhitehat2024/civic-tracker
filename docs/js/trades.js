(function () {
  var list = document.querySelector("#feed");
  var form = document.querySelector("#filters");
  var search = document.querySelector("#q");
  var chamber = document.querySelector("#chamber");
  var party = document.querySelector("#party");
  var typeInput = document.querySelector("#type");
  var owner = document.querySelector("#owner");
  var fromInput = document.querySelector("#from");
  var toInput = document.querySelector("#to");
  var sortSelect = document.querySelector("#sort");
  var countEl = document.querySelector("#count");
  var clearBtn = document.querySelector("#clear");
  var data = { updated: null, items: [] };
  var sortState = { key: "filing", dir: "desc" };

  function items() {
    return Array.isArray(data.items) ? data.items : [];
  }

  function whenOf(item) {
    return Civic.day(item.transactionDate || item.filingDate);
  }

  function amountStart(value) {
    var match = String(value || "").replace(/,/g, "").match(/(\d+)/);
    if (!match) return null;
    if (/see official/i.test(String(value || ""))) return null;
    return Number(match[1]);
  }

  function matches(item) {
    if (chamber.value && item.chamber !== chamber.value) return false;
    if (!Civic.partyMatches(item.party, party.value)) return false;
    if (typeInput.value && item.transactionType !== typeInput.value) return false;
    if (owner.value === "none" && item.owner) return false;
    if (owner.value && owner.value !== "none" && String(item.owner || "").toLowerCase() !== owner.value) return false;
    var when = whenOf(item);
    if (fromInput.value && (!when || when < fromInput.value)) return false;
    if (toInput.value && (!when || when > toInput.value)) return false;
    var query = search.value.trim().toLowerCase();
    if (!query) return true;
    var haystack = [item.member, item.asset, item.ticker, item.state, item.amountRange, Civic.tradeTypeLabel(item.transactionType), item.owner]
      .join(" ")
      .toLowerCase();
    return haystack.indexOf(query) !== -1;
  }

  function compareText(left, right) {
    if (left < right) return -1;
    if (left > right) return 1;
    return 0;
  }

  function sortItems(rows) {
    var dir = sortState.dir === "asc" ? 1 : -1;
    return rows.slice().sort(function (a, b) {
      var result = 0;
      if (sortState.key === "amount") {
        var leftAmount = amountStart(a.amountRange);
        var rightAmount = amountStart(b.amountRange);
        if (leftAmount === null && rightAmount === null) result = 0;
        else if (leftAmount === null) return 1;
        else if (rightAmount === null) return -1;
        else result = (leftAmount - rightAmount) * dir;
      } else {
        var left = "";
        var right = "";
        if (sortState.key === "date") {
          left = whenOf(a);
          right = whenOf(b);
        } else if (sortState.key === "filing") {
          left = Civic.day(a.filingDate);
          right = Civic.day(b.filingDate);
        } else if (sortState.key === "member") {
          left = String(a.member || "").toLowerCase();
          right = String(b.member || "").toLowerCase();
        } else if (sortState.key === "asset") {
          left = String(a.asset || "").toLowerCase();
          right = String(b.asset || "").toLowerCase();
        } else if (sortState.key === "type") {
          left = Civic.tradeTypeLabel(a.transactionType).toLowerCase();
          right = Civic.tradeTypeLabel(b.transactionType).toLowerCase();
        } else if (sortState.key === "chamber") {
          left = Civic.chamberLabel(a.chamber).toLowerCase();
          right = Civic.chamberLabel(b.chamber).toLowerCase();
        }
        result = compareText(left, right) * dir;
      }
      if (result === 0) result = compareText(String(a.id || ""), String(b.id || ""));
      return result;
    });
  }

  function syncSortSelect() {
    var value = sortState.key + "-" + sortState.dir;
    if (sortSelect.querySelector('option[value="' + value + '"]')) sortSelect.value = value;
  }

  function writeQuery() {
    Civic.writeParams({
      q: search.value.trim(),
      chamber: chamber.value,
      party: party.value,
      type: typeInput.value,
      owner: owner.value,
      from: fromInput.value,
      to: toInput.value,
      sort: sortSelect.value !== "filing-desc" ? sortSelect.value : "",
    });
  }

  function setCount(shown, total) {
    var noun = shown === 1 ? "trade record" : "trade records";
    countEl.textContent = shown === total
      ? "Showing " + shown.toLocaleString() + " " + noun + "."
      : "Showing " + shown.toLocaleString() + " of " + total.toLocaleString() + " trade records.";
  }

  function noteFor(item) {
    if (item.transactionType === "scanned filing") return "The official filing is a scanned document.";
    if (item.transactionType === "senate-efd-search") return "Individual transactions are listed on the Senate's official financial disclosure search.";
    return "";
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
      countEl.textContent = "No trade records are posted yet.";
      Civic.showMessage(list, "No congressional trade records are posted yet. Check back after the next daily update.");
      writeQuery();
      return;
    }
    var shown = sortItems(rows.filter(matches));
    setCount(shown.length, rows.length);
    if (shown.length === 0) {
      list.replaceChildren();
      var box = Civic.el("div", "empty");
      var message = Civic.el("p", null, "No trade records match these filters. Try another member, party, or date range.");
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
    table.appendChild(Civic.el("caption", "sr-only", countEl.textContent + " Sorted by " + sortState.key + ", " + sortState.dir + "."));
    var head = Civic.el("thead");
    var headRow = Civic.el("tr");
    [
      ["Date", "date"],
      ["Member", "member"],
      ["Transaction", "type"],
      ["Asset", "asset"],
      ["Amount", "amount"],
      ["Filed", "filing"],
    ].forEach(function (pair) {
      headRow.appendChild(headerCell(pair[0], pair[1]));
    });
    head.appendChild(headRow);
    table.appendChild(head);

    var body = Civic.el("tbody");
    shown.forEach(function (item) {
      var row = Civic.el("tr");

      var dateCell = Civic.el("td");
      var acted = item.transactionDate || item.filingDate;
      dateCell.appendChild(Civic.timeEl(acted));
      if (!item.transactionDate && item.filingDate) {
        dateCell.appendChild(Civic.el("span", "subline", "Filing date"));
      }
      row.appendChild(dateCell);

      var memberCell = Civic.el("td");
      memberCell.appendChild(Civic.el("span", "member-name", item.member || "Member"));
      var meta = [Civic.chamberLabel(item.chamber), item.state].filter(Boolean).join(" · ");
      if (meta) memberCell.appendChild(Civic.el("span", "subline", meta));
      var partyName = Civic.partyLabel(item.party);
      if (partyName) memberCell.appendChild(Civic.el("span", Civic.partyClass(item.party), partyName));
      else memberCell.appendChild(Civic.el("span", "subline", "Party not listed"));
      row.appendChild(memberCell);

      var typeCell = Civic.el("td");
      typeCell.appendChild(Civic.el("span", Civic.tradeTypeClass(item.transactionType), Civic.tradeTypeLabel(item.transactionType)));
      row.appendChild(typeCell);

      var assetCell = Civic.el("td", "action-cell");
      assetCell.appendChild(Civic.el("span", "asset-name", item.asset || "Asset not named"));
      if (item.ticker) assetCell.appendChild(Civic.el("span", "ticker", item.ticker));
      var note = noteFor(item);
      if (note) assetCell.appendChild(Civic.el("span", "subline", note));
      var record = Civic.officialLink(item.url, item.transactionType === "senate-efd-search" ? "Senate disclosure search" : "Official filing");
      if (record) assetCell.appendChild(record);
      row.appendChild(assetCell);

      var amountCell = Civic.el("td", "amount");
      amountCell.appendChild(Civic.el("span", "amount-range", item.amountRange || "—"));
      var ownerName = Civic.ownerLabel(item.owner);
      if (ownerName) amountCell.appendChild(Civic.el("span", "subline", "Owner: " + ownerName));
      row.appendChild(amountCell);

      var filedCell = Civic.el("td");
      if (item.filingDate) filedCell.appendChild(Civic.timeEl(item.filingDate));
      else filedCell.textContent = "—";
      row.appendChild(filedCell);

      body.appendChild(row);
    });
    table.appendChild(body);

    var scroller = Civic.el("div", "table-scroll");
    scroller.tabIndex = 0;
    scroller.setAttribute("role", "region");
    scroller.setAttribute("aria-label", "Congressional trades table");
    scroller.appendChild(table);
    list.replaceChildren(scroller);
    writeQuery();
  }

  function addOption(select, value, label) {
    var option = Civic.el("option", null, label);
    option.value = value;
    select.appendChild(option);
  }

  function fillChoices(rows) {
    var types = [];
    var owners = [];
    rows.forEach(function (item) {
      if (item.transactionType && types.indexOf(item.transactionType) === -1) types.push(item.transactionType);
      if (item.owner && owners.indexOf(String(item.owner).toLowerCase()) === -1) owners.push(String(item.owner).toLowerCase());
    });
    types.sort();
    owners.sort();
    types.forEach(function (value) { addOption(typeInput, value, Civic.tradeTypeLabel(value)); });
    owners.forEach(function (value) { addOption(owner, value, Civic.ownerLabel(value)); });
    addOption(owner, "none", "Not listed");
  }

  function optionExists(select, value) {
    for (var i = 0; i < select.options.length; i++) {
      if (select.options[i].value === value) return true;
    }
    return false;
  }

  function applySortValue(value) {
    var parts = String(value || "date-desc").split("-");
    var dir = parts.pop();
    var key = parts.join("-");
    if (dir !== "asc" && dir !== "desc") return;
    sortState.key = key || "date";
    sortState.dir = dir;
  }

  function readQuery() {
    var params = Civic.readParams();
    if (params.get("q")) search.value = params.get("q");
    ["chamber", "party"].forEach(function (name) {
      var input = name === "chamber" ? chamber : party;
      var value = params.get(name);
      if (value && optionExists(input, value)) input.value = value;
    });
    if (params.get("type") && optionExists(typeInput, params.get("type"))) typeInput.value = params.get("type");
    if (params.get("owner") && optionExists(owner, params.get("owner"))) owner.value = params.get("owner");
    if (params.get("from")) fromInput.value = params.get("from");
    if (params.get("to")) toInput.value = params.get("to");
    if (params.get("sort") && optionExists(sortSelect, params.get("sort"))) {
      sortSelect.value = params.get("sort");
      applySortValue(params.get("sort"));
    }
  }

  function resetFilters() {
    form.reset();
    sortState = { key: "filing", dir: "desc" };
    sortSelect.value = "filing-desc";
    render();
  }

  form.addEventListener("submit", function (event) { event.preventDefault(); });
  [search, chamber, party, typeInput, owner, fromInput, toInput].forEach(function (input) {
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
      sortState.dir = key === "member" || key === "asset" || key === "type" || key === "chamber" ? "asc" : "desc";
    }
    syncSortSelect();
    render();
  });

  Civic.loadFeed("data/trades.json")
    .then(function (json) {
      data = json && typeof json === "object" ? json : { items: [] };
      Civic.noteUpdated(data.updated);
      fillChoices(items());
      readQuery();
      render();
    })
    .catch(function () {
      countEl.textContent = "";
      Civic.noteUpdated(null);
      Civic.showMessage(list, "Trade records could not be loaded. Refresh the page to try again.");
    });
})();
