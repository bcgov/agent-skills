/**
 * search.js – client-side full-text search for AI Services Hub docs.
 *
 * Features
 * --------
 * • Loads assets/search-index.json (built at deploy time by generate-search-index.js)
 * • Uses FlexSearch (assets/flexsearch.bundle.js) for fast full-text querying
 * • Opens a full-screen modal from the header search button (or Ctrl/Cmd+K)
 * • Shows matching sections: page title + section heading + contextual excerpt
 * • Cross-page: navigates to target page with URL params for breadcrumb injection
 * • Same-page: smooth-scrolls to section without reload
 * • Breadcrumb bar injected at top of <main> after arriving from a search result
 * • Target section briefly highlighted (gold flash animation)
 */

(function () {
  "use strict";

  // -------------------------------------------------------------------------
  // State
  // -------------------------------------------------------------------------
  var searchIndex = null; // raw array from search-index.json (for data lookup)
  var flexIndex = null; // FlexSearch Document index (for querying)
  var modal, searchInput, resultsContainer, searchBtn, breadcrumbEl;
  var debounceTimer = null;
  var MAX_RESULTS = 25;

  // -------------------------------------------------------------------------
  // Utilities
  // -------------------------------------------------------------------------

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  /** Wrap occurrences of `query` in <mark> within `text` (HTML-escaped). */
  function highlightMatches(text, query) {
    var safe = escapeHtml(text);
    if (!query) return safe;
    try {
      var re = new RegExp("(" + escapeRegex(query) + ")", "gi");
      return safe.replace(re, "<mark>$1</mark>");
    } catch (e) {
      return safe;
    }
  }

  /**
   * Return a short excerpt centred around the first occurrence of `query`
   * within `fullText`.
   */
  function excerptAround(fullText, query, maxLen) {
    maxLen = maxLen || 200;
    if (!fullText) return "";
    if (!query)
      return fullText.slice(0, maxLen) + (fullText.length > maxLen ? "…" : "");

    var idx = fullText.toLowerCase().indexOf(query.toLowerCase());
    if (idx === -1) {
      return fullText.slice(0, maxLen) + (fullText.length > maxLen ? "…" : "");
    }

    var halfWin = Math.floor(maxLen / 2);
    var start = Math.max(0, idx - halfWin + Math.floor(query.length / 2));
    var end = Math.min(fullText.length, start + maxLen);
    // Adjust start if we hit the end boundary
    start = Math.max(0, end - maxLen);

    var prefix = start > 0 ? "…" : "";
    var suffix = end < fullText.length ? "…" : "";
    return prefix + fullText.slice(start, end) + suffix;
  }

  /** Best-effort current page filename, e.g. "playbooks.html". */
  function currentPageFilename() {
    var parts = window.location.pathname.split("/");
    var last = parts[parts.length - 1];
    return last || "index.html";
  }

  // -------------------------------------------------------------------------
  // Index loading
  // -------------------------------------------------------------------------

  function loadIndex() {
    // Resolve path relative to this script so it works regardless of sub-path.
    var scriptEl = document.getElementById("search-script");
    var base = scriptEl
      ? scriptEl.src.replace(/search\.js(\?.*)?$/, "")
      : "assets/";

    fetch(base + "search-index.json")
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        searchIndex = data;

        // Build a FlexSearch Document index over the three indexed fields.
        // Fields: sectionTitle (weight 3), pageTitle (weight 1), text (weight 2).
        flexIndex = new FlexSearch.Document({
          tokenize: "forward",
          cache: 100,
          document: {
            id: "idx",
            index: [
              { field: "sectionTitle", tokenize: "full" },
              { field: "pageTitle" },
              { field: "text", tokenize: "full" },
            ],
          },
        });

        for (var i = 0; i < data.length; i++) {
          flexIndex.add({
            idx: i,
            sectionTitle: data[i].sectionTitle,
            pageTitle: data[i].pageTitle,
            text: data[i].text,
          });
        }
      })
      .catch(function (err) {
        console.warn("[search] Could not load search index:", err);
      });
  }

  // -------------------------------------------------------------------------
  // Modal open / close
  // -------------------------------------------------------------------------

  function openModal() {
    if (!modal) return;
    modal.classList.add("search-modal--active");
    searchInput.focus();
    searchInput.select();
    document.body.style.overflow = "hidden";
  }

  function closeModal() {
    if (!modal) return;
    modal.classList.remove("search-modal--active");
    resultsContainer.innerHTML = "";
    searchInput.value = "";
    document.body.style.overflow = "";
  }

  // -------------------------------------------------------------------------
  // Search logic
  // -------------------------------------------------------------------------

  function doSearch(rawQuery) {
    var query = rawQuery.trim();

    if (!query) {
      resultsContainer.innerHTML = "";
      return;
    }

    if (!flexIndex || !searchIndex) {
      resultsContainer.innerHTML =
        '<div class="search-loading">Loading index…</div>';
      return;
    }

    // Query all three fields; assign field weights for deduped scoring.
    var fieldWeight = { sectionTitle: 3, text: 2, pageTitle: 1 };
    var scores = {}; // idx → cumulative score

    var fieldResults = flexIndex.search(query, MAX_RESULTS);
    for (var f = 0; f < fieldResults.length; f++) {
      var field = fieldResults[f].field;
      var weight = fieldWeight[field] || 1;
      var ids = fieldResults[f].result;
      for (var r = 0; r < ids.length; r++) {
        var id = ids[r];
        scores[id] = (scores[id] || 0) + weight;
      }
    }

    // Sort by score descending, look up raw entries.
    var ranked = Object.keys(scores)
      .map(function (id) {
        return { id: Number(id), score: scores[id] };
      })
      .sort(function (a, b) {
        return b.score - a.score;
      })
      .slice(0, MAX_RESULTS)
      .map(function (x) {
        return searchIndex[x.id];
      });

    renderResults(ranked, query);
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  function renderResults(results, query) {
    if (results.length === 0) {
      resultsContainer.innerHTML =
        '<div class="search-no-results">' +
        '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>' +
        "<p>No results for <strong>" +
        escapeHtml(query) +
        "</strong></p>" +
        "</div>";
      return;
    }

    var html = results
      .map(function (item) {
        var excerptText = excerptAround(item.text, query, 200);
        var href =
          item.page +
          "?from=" +
          encodeURIComponent(item.pageTitle) +
          "&section=" +
          encodeURIComponent(item.sectionTitle) +
          "#" +
          encodeURIComponent(item.sectionId);

        return (
          '<a class="search-result-item"' +
          ' href="' +
          escapeHtml(href) +
          '"' +
          ' data-page="' +
          escapeHtml(item.page) +
          '"' +
          ' data-section-id="' +
          escapeHtml(item.sectionId) +
          '"' +
          ' data-page-title="' +
          escapeHtml(item.pageTitle) +
          '"' +
          ' data-section-title="' +
          escapeHtml(item.sectionTitle) +
          '">' +
          '<div class="search-result-meta">' +
          escapeHtml(item.pageTitle) +
          "</div>" +
          '<div class="search-result-title">' +
          highlightMatches(item.sectionTitle, query) +
          "</div>" +
          '<div class="search-result-excerpt">' +
          highlightMatches(excerptText, query) +
          "</div>" +
          "</a>"
        );
      })
      .join("");

    resultsContainer.innerHTML =
      '<div class="search-count">' +
      results.length +
      " result" +
      (results.length !== 1 ? "s" : "") +
      "</div>" +
      html;
  }

  // -------------------------------------------------------------------------
  // Result click – handle same-page navigation without reload
  // -------------------------------------------------------------------------

  function handleResultClick(e) {
    var item = e.target.closest(".search-result-item");
    if (!item) return;

    var targetPage = item.dataset.page;
    var sectionId = item.dataset.sectionId;
    var sectionTitle = item.dataset.sectionTitle;
    var pageTitle = item.dataset.pageTitle;

    if (targetPage !== currentPageFilename()) {
      // Cross-page: let default navigation happen; breadcrumb is set on arrival.
      closeModal();
      return;
    }

    // Same-page: prevent full reload, scroll + highlight + breadcrumb.
    e.preventDefault();
    closeModal();

    showBreadcrumb(pageTitle, sectionTitle);

    var target = document.getElementById(sectionId);
    if (target) {
      var header = document.querySelector(".bc-header");
      var headerH = header ? header.offsetHeight : 72;
      var top =
        target.getBoundingClientRect().top + window.pageYOffset - headerH - 16;
      window.scrollTo({ top: top, behavior: "smooth" });
      flashHighlight(target);
    }
  }

  // -------------------------------------------------------------------------
  // Breadcrumb
  // -------------------------------------------------------------------------

  function showBreadcrumb(pageTitle, sectionTitle) {
    if (!breadcrumbEl) return;
    var currentPage = currentPageFilename();

    var inner =
      '<nav class="breadcrumb-nav" aria-label="Search breadcrumb">' +
      '<a href="index.html">Home</a>' +
      '<span class="breadcrumb-sep" aria-hidden="true">›</span>' +
      '<a href="' +
      escapeHtml(currentPage) +
      '">' +
      escapeHtml(pageTitle) +
      "</a>";

    if (sectionTitle && sectionTitle !== pageTitle) {
      inner +=
        '<span class="breadcrumb-sep" aria-hidden="true">›</span>' +
        '<span class="breadcrumb-current">' +
        escapeHtml(sectionTitle) +
        "</span>";
    }

    inner += "</nav>";
    breadcrumbEl.innerHTML = inner;
    breadcrumbEl.style.display = "block";
  }

  function initBreadcrumbFromUrl() {
    var params = new URLSearchParams(window.location.search);
    var from = params.get("from");
    var section = params.get("section");

    if (!from) return;
    showBreadcrumb(from, section || "");

    // Clean query params from the address bar (keep hash).
    if (history && history.replaceState) {
      history.replaceState(
        null,
        "",
        window.location.pathname + window.location.hash,
      );
    }
  }

  // -------------------------------------------------------------------------
  // Section highlight flash
  // -------------------------------------------------------------------------

  function flashHighlight(el) {
    el.classList.remove("search-highlight"); // reset if already running
    // Force reflow so the animation restarts
    void el.offsetWidth;
    el.classList.add("search-highlight");
    setTimeout(function () {
      el.classList.remove("search-highlight");
    }, 2200);
  }

  function initHighlightFromHash() {
    var hash = window.location.hash;
    if (!hash) return;
    // Small delay ensures the page has settled (especially after scrollIntoView).
    setTimeout(function () {
      try {
        var target = document.querySelector(hash);
        if (target) flashHighlight(target);
      } catch (e) {
        // Invalid selector (e.g. numeric IDs) – ignore.
      }
    }, 350);
  }

  // -------------------------------------------------------------------------
  // Boot
  // -------------------------------------------------------------------------

  document.addEventListener("DOMContentLoaded", function () {
    modal = document.getElementById("search-modal");
    searchInput = document.getElementById("search-input");
    resultsContainer = document.getElementById("search-results");
    searchBtn = document.getElementById("search-btn");
    breadcrumbEl = document.getElementById("search-breadcrumb");

    if (!modal) return; // safety – header partial not injected yet

    loadIndex();
    initBreadcrumbFromUrl();
    initHighlightFromHash();

    // ---- open triggers ----
    if (searchBtn) {
      searchBtn.addEventListener("click", openModal);
    }

    // Ctrl/Cmd + K
    document.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        if (modal.classList.contains("search-modal--active")) {
          closeModal();
        } else {
          openModal();
        }
      }
    });

    // ---- close triggers ----
    var closeBtn = document.getElementById("search-modal-close");
    if (closeBtn) closeBtn.addEventListener("click", closeModal);

    // Click outside modal box
    modal.addEventListener("click", function (e) {
      if (e.target === modal) closeModal();
    });

    // Escape key
    document.addEventListener("keydown", function (e) {
      if (
        e.key === "Escape" &&
        modal.classList.contains("search-modal--active")
      ) {
        closeModal();
      }
    });

    // ---- search input ----
    searchInput.addEventListener("input", function () {
      clearTimeout(debounceTimer);
      var val = this.value;
      debounceTimer = setTimeout(function () {
        doSearch(val);
      }, 180);
    });

    // Keyboard navigation within results
    searchInput.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        var first = resultsContainer.querySelector(".search-result-item");
        if (first) first.focus();
      }
    });

    resultsContainer.addEventListener("keydown", function (e) {
      var items = Array.from(
        resultsContainer.querySelectorAll(".search-result-item"),
      );
      var idx = items.indexOf(document.activeElement);
      if (e.key === "ArrowDown" && idx < items.length - 1) {
        e.preventDefault();
        items[idx + 1].focus();
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (idx === 0) {
          searchInput.focus();
        } else if (idx > 0) {
          items[idx - 1].focus();
        }
      }
    });

    // ---- result clicks ----
    resultsContainer.addEventListener("click", handleResultClick);
  });
})();
