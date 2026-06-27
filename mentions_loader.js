/**
 * mentions_loader.js
 * Fetches the three workflow JSON files and populates each term card
 * with every pain-point and feature line that mentions that term.
 * Included by subprocess.html, forms.html, and personnel.html.
 */
(function () {
  'use strict';

  var SOURCES = [
    { key: 'operations', label: 'Operations', json: '02_operations_content.json' },
    { key: 'sales',      label: 'Sales',      json: '03_sales_content.json' },
    { key: 'accounting', label: 'Accounting', json: '04_accounting_content.json' }
  ];

  /* Extract a leading reference code like "I5A.1.1" or "A5C2.1.1" */
  function extractCode(text) {
    var m = String(text).match(/^([A-Za-z][0-9A-Za-z]*(?:[A-Za-z][0-9A-Za-z]*)*(?:\.[0-9A-Za-z]+)+)/);
    return m ? m[1] : null;
  }

  function fetchJSON(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status + ' ' + url);
      return r.json();
    });
  }

  function findMentions(term, sourceKey, data) {
    var results = [];
    var tl = term.toLowerCase();

    /* Current workflow — manual_stages pain_points */
    var mstages = data.manual_stages || [];
    mstages.forEach(function (stage, si) {
      (stage.pain_points || []).forEach(function (pp, pi) {
        if (String(pp).toLowerCase().indexOf(tl) !== -1) {
          results.push({
            text: String(pp),
            anchor: 'pp-' + sourceKey + '-' + si + '-' + pi,
            section: stage.english || ('Stage ' + (si + 1)),
            tabKey: sourceKey,
            type: 'current'
          });
        }
      });
    });

    /* Future workflow — stages → cards → features */
    var stages = data.stages || [];
    stages.forEach(function (stage, si) {
      (stage.cards || []).forEach(function (card, ci) {
        (card.features || []).forEach(function (feat, fi) {
          if (String(feat).toLowerCase().indexOf(tl) !== -1) {
            results.push({
              text: String(feat),
              anchor: 'feat-' + sourceKey + '-' + si + '-' + ci + '-' + fi,
              section: (stage.romaji || ('Stage ' + (si + 1))) + ' · ' + (card.name || ''),
              tabKey: sourceKey,
              type: 'future'
            });
          }
        });
      });
    });

    return results;
  }

  /* Navigate parent frame to a tab+anchor */
  window.xmGo = function (tabKey, anchorId) {
    if (window.parent && typeof window.parent.activateTabById === 'function') {
      window.parent.activateTabById(tabKey, anchorId);
    } else {
      window.location.href = tabKey + '.html#' + anchorId;
    }
  };

  /* Build the HTML for one card's mention block */
  function buildMentionsHTML(allMentions) {
    if (!allMentions.length) {
      return '<div class="xm-empty">Not mentioned in current workflow data.</div>';
    }

    /* Group by source tab */
    var order = [];
    var grouped = {};
    allMentions.forEach(function (m) {
      if (!grouped[m.tabKey]) { grouped[m.tabKey] = []; order.push(m.tabKey); }
      grouped[m.tabKey].push(m);
    });

    var html = '';
    order.forEach(function (key) {
      var items = grouped[key];
      var label = key.charAt(0).toUpperCase() + key.slice(1);
      html += '<div class="xm-group">';
      html += '<div class="xm-group-lbl">' + label + ' <span class="xm-cnt">(' + items.length + ')</span></div>';
      items.forEach(function (m) {
        var code = extractCode(m.text);
        var displayCode = code
          ? code
          : (m.text.length > 32 ? m.text.slice(0, 32) + '…' : m.text);
        var badge = m.type === 'current' ? 'Current' : 'Future';
        var bClass = 'xm-badge xm-badge-' + m.type;
        var safeTitle = m.text.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
        var safeKey = m.tabKey.replace(/'/g, "\\'");
        var safeAnchor = m.anchor.replace(/'/g, "\\'");
        html += '<div class="xm-item">'
          + '<a class="xm-link" href="#" title="' + safeTitle + '" '
          + 'onclick="window.xmGo&&window.xmGo(\'' + safeKey + '\',\'' + safeAnchor + '\');return false">'
          + '<span class="xm-code">' + displayCode + '</span>'
          + '<span class="' + bClass + '">' + badge + '</span>'
          + '</a>'
          + '<div class="xm-full">' + m.text.replace(/&/g, '&amp;').replace(/</g, '&lt;') + '</div>'
          + '</div>';
      });
      html += '</div>';
    });
    return html;
  }

  /* Main: inject mentions into every .term-card */
  var cards = Array.prototype.slice.call(document.querySelectorAll('.term-card'));
  if (!cards.length) return;

  /* Inject loading placeholders */
  cards.forEach(function (card) {
    var inner = card.querySelector('.term-inner');
    if (!inner) return;
    var div = document.createElement('div');
    div.className = 'xref-mentions td-group';
    div.innerHTML = '<div class="td-label xm-section-lbl">Workflow Mentions</div>'
      + '<div class="xm-loading">Loading…</div>';
    inner.appendChild(div);
  });

  /* Fetch all workflow JSONs */
  Promise.all(SOURCES.map(function (src) {
    return fetchJSON(src.json)
      .then(function (data) { return { key: src.key, data: data }; })
      .catch(function () { return { key: src.key, data: {} }; });
  })).then(function (results) {
    cards.forEach(function (card) {
      var nameEl = card.querySelector('.term-name');
      if (!nameEl) return;
      var term = nameEl.textContent.trim();

      var allMentions = [];
      results.forEach(function (r) {
        allMentions = allMentions.concat(findMentions(term, r.key, r.data));
      });

      var mentionsDiv = card.querySelector('.xref-mentions');
      if (!mentionsDiv) return;
      var loadingEl = mentionsDiv.querySelector('.xm-loading');
      if (loadingEl) loadingEl.outerHTML = buildMentionsHTML(allMentions);
    });
  });
})();
