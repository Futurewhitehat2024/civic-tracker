(function () {
  var list = document.querySelector("#feed");
  var memberInput = document.querySelector("#member");
  var chamberInput = document.querySelector("#chamber");
  var partyInput = document.querySelector("#party");
  var fromInput = document.querySelector("#from");
  var toInput = document.querySelector("#to");
  var meta = document.querySelector("#updated");
  var data = { updated: null, items: [] };

  function partyMatches(value, filter) {
    if (!filter) {
      return true;
    }
    var party = String(value || "").trim().toLowerCase();
    if (filter === "Democratic") {
      return party === "d" || party === "democratic" || party.indexOf("democrat") === 0;
    }
    if (filter === "Republican") {
      return party === "r" || party === "republican" || party.indexOf("republican") === 0;
    }
    if (filter === "Independent") {
      return party === "i" || party === "independent";
    }
    return party === filter.toLowerCase();
  }

  function day(value) {
    if (!value) {
      return "";
    }
    return String(value).slice(0, 10);
  }

  function matches(item) {
    var memberQuery = memberInput.value.trim().toLowerCase();
    if (memberQuery && String(item.member || "").toLowerCase().indexOf(memberQuery) === -1) {
      return false;
    }
    if (chamberInput.value && item.chamber !== chamberInput.value) {
      return false;
    }
    if (!partyMatches(item.party, partyInput.value)) {
      return false;
    }
    var when = day(item.transactionDate || item.filingDate);
    if (fromInput.value && (!when || when < fromInput.value)) {
      return false;
    }
    if (toInput.value && (!when || when > toInput.value)) {
      return false;
    }
    return true;
  }

  function headline(item) {
    var who = item.member || "A member of Congress";
    var action = item.transactionType || "transaction";
    var article = /^[aeiou]/i.test(action) ? "an" : "a";
    var asset = item.ticker ? item.ticker + " (" + (item.asset || "asset") + ")" : item.asset || "an asset";
    var amount = item.amountRange ? " (" + item.amountRange + ")" : "";
    var when = item.transactionDate || item.filingDate;
    return who + " reported " + article + " " + action + " of " + asset + amount + (when ? ", dated " + when : "") + ".";
  }

  function render() {
    var items = Array.isArray(data.items) ? data.items : [];
    if (items.length === 0) {
      Civic.showMessage(list, Civic.EMPTY);
      return;
    }
    var shown = items.filter(matches);
    if (shown.length === 0) {
      Civic.showMessage(list, "No filings match these filters.");
      return;
    }
    list.replaceChildren();
    shown.forEach(function (item) {
      var article = document.createElement("article");
      article.className = "card";
      var heading = document.createElement("h2");
      heading.textContent = headline(item);
      article.appendChild(heading);

      var details = document.createElement("p");
      details.className = "meta";
      details.textContent = [
        item.chamber === "senate" ? "Senate" : item.chamber === "house" ? "House" : item.chamber,
        item.party,
        item.state,
        item.owner ? "Owner: " + item.owner : "",
        item.filingDate ? "Filed " + item.filingDate : "",
      ]
        .filter(Boolean)
        .join(" · ");
      article.appendChild(details);

      var href = Civic.safeUrl(item.url);
      if (href) {
        var link = document.createElement("a");
        link.href = href;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = "Official filing";
        article.appendChild(link);
      }
      list.appendChild(article);
    });
  }

  document.querySelector("#filters").addEventListener("submit", function (event) {
    event.preventDefault();
  });
  [memberInput, chamberInput, partyInput, fromInput, toInput].forEach(function (el) {
    el.addEventListener("input", render);
    el.addEventListener("change", render);
  });

  Civic.loadFeed("data/trades.json")
    .then(function (json) {
      data = json && typeof json === "object" ? json : { items: [] };
      meta.textContent = data.updated
        ? "Updated " + Civic.formatWhen(data.updated)
        : "Not yet updated.";
      render();
    })
    .catch(function () {
      meta.textContent = "";
      Civic.showMessage(list, "Could not load trades data.");
    });
})();
