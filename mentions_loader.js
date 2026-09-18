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
    var stages = data.stages || [];
    var idPrefix = sourceKey; // matches id_prefix = f'{page_key}-{si}' in workflow_generate.py

    function scanList(list, kind, anchorTag, label) {
      (list || []).forEach(function (text, ti) {
        if (String(text).toLowerCase().indexOf(tl) !== -1) {
          results.push({
            text: String(text),
            anchor: idPrefix + '-' + anchorTag + '-' + ti,
            section: label,
            tabKey: sourceKey,
            type: kind
          });
        }
      });
    }

    stages.forEach(function (stage, si) {
      idPrefix = sourceKey + '-' + si;
      var stageLabel = stage.romaji || ('Stage ' + (si + 1));
      scanList(stage.sop_steps, 'current', 'sop', stageLabel + ' · SOP Manual (Current Procedures)');
      scanList(stage.guidelines, 'current', 'gl', stageLabel + ' · Operational Guidelines');
      // future_procedures (TSV-migrated stages) shares the row's "sop" anchor
      // with its paired current step -- same table row, same hyperlink target
      // -- so a Future mention jumps to the exact same spot a Current mention
      // for that row would. The badge/type label still reads "Future" (vs.
      // "Current") since that comes from `kind`, not the anchor tag. Stages
      // not yet migrated only have the old print-only current_future bullets,
      // which stay unscanned since a Workflow Mentions link should always
      // land somewhere visible.
      scanList(stage.future_procedures, 'future', 'sop', stageLabel + ' · SOP Manual (Future Procedures)');
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

  /* Group a list of same-type mentions by source tab and render them */
  function buildGroupedList(mentions, emptyMsg) {
    if (!mentions.length) {
      return '<div class="xm-empty">' + emptyMsg + '</div>';
    }
    var order = [];
    var grouped = {};
    mentions.forEach(function (m) {
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
        var safeTitle = m.text.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
        var safeKey = m.tabKey.replace(/'/g, "\\'");
        var safeAnchor = m.anchor.replace(/'/g, "\\'");
        html += '<div class="xm-item">'
          + '<a class="xm-link" href="#" title="' + safeTitle + '" '
          + 'onclick="window.xmGo&&window.xmGo(\'' + safeKey + '\',\'' + safeAnchor + '\');return false">'
          + '<span class="xm-code">' + displayCode + '</span>'
          + '</a>'
          + '<div class="xm-full">' + m.text.replace(/&/g, '&amp;').replace(/</g, '&lt;') + '</div>'
          + '</div>';
      });
      html += '</div>';
    });
    return html;
  }

  /* Main: inject Current Procedures / Future Procedures columns into every .term-card */
  var cards = Array.prototype.slice.call(document.querySelectorAll('.term-card'));
  if (!cards.length) return;

  /* Inject loading placeholders -- two columns, same grid row, sitting
     alongside Field1/Field2 the same way the SOP Manual's Current/Future
     table sits side by side. */
  cards.forEach(function (card) {
    var inner = card.querySelector('.term-inner');
    if (!inner) return;
    var cur = document.createElement('div');
    cur.className = 'xref-mentions-cur';
    cur.innerHTML = '<div class="td-label xm-section-lbl">Current Procedures</div><div class="xm-loading">Loading…</div>';
    var fut = document.createElement('div');
    fut.className = 'xref-mentions-fut';
    fut.innerHTML = '<div class="td-label xm-section-lbl">Future Procedures</div><div class="xm-loading">Loading…</div>';
    inner.appendChild(cur);
    inner.appendChild(fut);
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
      var name = nameEl.textContent.trim();
      // Personnel cards also carry a role-chip (their position/title) --
      // SOP text very often refers to staff by role ("Logistics Officer
      // schedules the delivery") rather than by first name, so match on
      // both and merge the results.
      var roleEl = card.querySelector('.role-chip');
      var role = roleEl ? roleEl.textContent.trim() : '';
      var terms = [name];
      if (role && role.toLowerCase() !== name.toLowerCase()) terms.push(role);

      var allMentions = [];
      results.forEach(function (r) {
        terms.forEach(function (term) {
          allMentions = allMentions.concat(findMentions(term, r.key, r.data));
        });
      });
      // A line could contain both the name and the role (rare, but
      // possible) -- de-dupe so it doesn't show up twice.
      var seen = {};
      allMentions = allMentions.filter(function (m) {
        var key = m.tabKey + '|' + m.anchor + '|' + m.type;
        if (seen[key]) return false;
        seen[key] = true;
        return true;
      });
      var current = allMentions.filter(function (m) { return m.type === 'current'; });
      var future = allMentions.filter(function (m) { return m.type === 'future'; });

      var curDiv = card.querySelector('.xref-mentions-cur');
      if (curDiv) {
        curDiv.innerHTML = '<div class="td-label xm-section-lbl">Current Procedures</div>'
          + buildGroupedList(current, 'Not mentioned in current procedures.');
      }
      var futDiv = card.querySelector('.xref-mentions-fut');
      if (futDiv) {
        futDiv.innerHTML = '<div class="td-label xm-section-lbl">Future Procedures</div>'
          + buildGroupedList(future, 'No future procedure recorded yet.');
      }
    });
  });
})();
