(function () {
  var federalCount = document.querySelector("#stat-federal");
  var tradeCount = document.querySelector("#stat-trades");
  var federalRange = document.querySelector("#stat-federal-range");
  var tradeRange = document.querySelector("#stat-trades-range");
  var note = document.querySelector("#stat-note");
  var federalList = document.querySelector("#latest-federal");
  var tradeList = document.querySelector("#latest-trades");

  function phrase(parts) {
    var bits = parts.filter(function (part) { return part.n > 0; }).map(function (part) {
      return part.n.toLocaleString() + " " + (part.n === 1 ? part.one : part.many);
    });
    if (!bits.length) return "";
    if (bits.length === 1) return bits[0];
    if (bits.length === 2) return bits[0] + " and " + bits[1];
    return bits.slice(0, -1).join(", ") + ", and " + bits[bits.length - 1];
  }

  function rangeLabel(dates) {
    var days = dates.filter(Boolean).sort();
    if (!days.length) return "";
    if (days[0] === days[days.length - 1]) return Civic.formatDate(days[0]);
    return Civic.formatDate(days[0]) + " – " + Civic.formatDate(days[days.length - 1]);
  }

  function latestItems(rows, pick, limit) {
    return rows.slice().sort(function (a, b) {
      var left = pick(a) || "";
      var right = pick(b) || "";
      if (left < right) return 1;
      if (left > right) return -1;
      return 0;
    }).slice(0, limit);
  }

  function renderFederal(feed) {
    var rows = feed && Array.isArray(feed.items) ? feed.items : [];
    federalCount.textContent = rows.length.toLocaleString();
    federalRange.textContent = rangeLabel(rows.map(function (item) { return Civic.day(item.date); }));
    if (!rows.length) {
      Civic.showMessage(federalList, "No federal actions are posted yet.");
      return "";
    }
    var counts = { bill: 0, vote: 0, executive_order: 0, federal_register: 0 };
    rows.forEach(function (item) {
      if (Object.prototype.hasOwnProperty.call(counts, item.kind)) counts[item.kind] += 1;
    });
    federalList.replaceChildren();
    latestItems(rows, function (item) { return Civic.day(item.date); }, 5).forEach(function (item) {
      federalList.appendChild(federalItem(item));
    });
    return phrase([
      { n: counts.federal_register, one: "Federal Register document", many: "Federal Register documents" },
      { n: counts.vote, one: "vote", many: "votes" },
      { n: counts.executive_order, one: "executive order", many: "executive orders" },
      { n: counts.bill, one: "bill", many: "bills" },
    ]);
  }

  function federalItem(item) {
    var article = Civic.el("article", "latest-item");
    var meta = Civic.el("p", "latest-meta");
    meta.appendChild(Civic.timeEl(item.date));
    meta.appendChild(Civic.el("span", Civic.kindClass(item.kind), Civic.kindLabel(item.kind)));
    article.appendChild(meta);
    var heading = Civic.el("h3");
    var link = Civic.officialLink(item.url, item.title || "Untitled action");
    if (link) {
      link.classList.add("title-link");
      heading.appendChild(link);
    } else heading.textContent = item.title || "Untitled action";
    article.appendChild(heading);
    var bits = [item.identifier, Civic.chamberLabel(item.chamber), item.source].filter(Boolean);
    if (bits.length) article.appendChild(Civic.el("p", "latest-sub", bits.join(" · ")));
    return article;
  }

  function renderTrades(feed) {
    var rows = feed && Array.isArray(feed.items) ? feed.items : [];
    tradeCount.textContent = rows.length.toLocaleString();
    tradeRange.textContent = rangeLabel(rows.reduce(function (days, item) {
      var acted = Civic.day(item.transactionDate);
      var filed = Civic.day(item.filingDate);
      if (acted) days.push(acted);
      if (filed) days.push(filed);
      return days;
    }, []));
    if (!rows.length) {
      Civic.showMessage(tradeList, "No trade records are posted yet.");
      return "";
    }
    var houseTx = 0;
    var scanned = 0;
    var senateLinks = 0;
    rows.forEach(function (item) {
      if (item.transactionType === "senate-efd-search") senateLinks += 1;
      else if (item.transactionType === "scanned filing") scanned += 1;
      else if (item.chamber === "house") houseTx += 1;
    });
    tradeList.replaceChildren();
    latestItems(rows, function (item) { return Civic.day(item.filingDate) || Civic.day(item.transactionDate); }, 5).forEach(function (item) {
      tradeList.appendChild(tradeItem(item));
    });
    return phrase([
      { n: houseTx, one: "House transaction", many: "House transactions" },
      { n: scanned, one: "scanned House filing", many: "scanned House filings" },
      { n: senateLinks, one: "Senate disclosure link", many: "Senate disclosure links" },
    ]);
  }

  function tradeItem(item) {
    var article = Civic.el("article", "latest-item");
    var meta = Civic.el("p", "latest-meta");
    meta.appendChild(Civic.timeEl(item.transactionDate || item.filingDate));
    meta.appendChild(Civic.el("span", Civic.tradeTypeClass(item.transactionType), Civic.tradeTypeLabel(item.transactionType)));
    article.appendChild(meta);
    var heading = Civic.el("h3");
    var who = item.member || "A member of Congress";
    var asset = item.ticker ? item.ticker + " · " + (item.asset || "asset") : (item.asset || "a disclosed asset");
    var title = item.transactionType === "senate-efd-search"
      ? who + " — Senate disclosure search"
      : item.transactionType === "scanned filing"
        ? who + " — scanned filing"
        : who + " · " + asset;
    var link = Civic.officialLink(item.url, title);
    if (link) {
      link.classList.add("title-link");
      heading.appendChild(link);
    } else heading.textContent = title;
    article.appendChild(heading);
    var bits = [Civic.chamberLabel(item.chamber), item.state, Civic.partyLabel(item.party), item.amountRange].filter(Boolean);
    if (item.transactionDate && item.filingDate && Civic.day(item.filingDate) !== Civic.day(item.transactionDate)) {
      bits.push("Filed " + Civic.formatDate(item.filingDate));
    }
    if (bits.length) article.appendChild(Civic.el("p", "latest-sub", bits.join(" · ")));
    return article;
  }

  Promise.all([
    Civic.loadFeed("data/federal.json").then(function (feed) { return { ok: true, feed: feed }; }).catch(function () { return { ok: false }; }),
    Civic.loadFeed("data/trades.json").then(function (feed) { return { ok: true, feed: feed }; }).catch(function () { return { ok: false }; }),
  ]).then(function (results) {
    var federal = results[0];
    var trades = results[1];
    var stamps = [];
    var notes = [];
    if (federal.ok) {
      if (federal.feed && federal.feed.updated) stamps.push(federal.feed.updated);
      var federalPhrase = renderFederal(federal.feed);
      if (federalPhrase) notes.push(federalPhrase);
    } else {
      federalCount.textContent = "—";
      Civic.showMessage(federalList, "Federal actions could not be loaded. Refresh the page to try again.");
    }
    if (trades.ok) {
      if (trades.feed && trades.feed.updated) stamps.push(trades.feed.updated);
      var tradePhrase = renderTrades(trades.feed);
      if (tradePhrase) notes.push(tradePhrase);
    } else {
      tradeCount.textContent = "—";
      Civic.showMessage(tradeList, "Trade records could not be loaded. Refresh the page to try again.");
    }
    Civic.noteUpdated(Civic.latestStamp(stamps));
    note.textContent = notes.length ? notes.join(". ") + "." : "";
  });
})();
