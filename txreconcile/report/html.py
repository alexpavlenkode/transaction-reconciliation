"""Eigenständiges HTML-Dashboard (eine Datei, keine externen Abhängigkeiten).

Die Daten liegen als JSON in der Seite (dieselbe Struktur wie ``report.json``); Filter, Sortierung und
Darstellung übernimmt etwas Vanilla-JavaScript. Dadurch funktioniert die Datei offline per Doppelklick.
"""
from __future__ import annotations

import json

from ..reconcile import ReconciliationResult
from .exports import result_to_dict

MAX_MATCHED_IN_HTML = 1000     # größere Tabellen machen die Seite träge; report.json/matched.csv enthalten alles

_TEMPLATE = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Transaktionsabgleich</title>
<style>
:root {
  --bg: #f6f7f9; --card: #ffffff; --text: #1c2430; --muted: #667085; --line: #e3e7ee;
  --high: #c62828; --high-bg: #fdecea; --med: #b26a00; --med-bg: #fff4e0; --low: #8a7a00; --low-bg: #fbf7da;
  --ok: #1b7f4b; --accent: #2557d6; --bar: #7a9cf0;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #12161c; --card: #1b212a; --text: #e6eaf0; --muted: #9aa5b5; --line: #2c3541;
    --high: #ff8a80; --high-bg: #3a1f1f; --med: #ffb74d; --med-bg: #3a2c14; --low: #e6d96a; --low-bg: #343012;
    --ok: #66d9a0; --accent: #8aa8ff; --bar: #4a6bc4;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
       font: 14px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
main { max-width: 1280px; margin: 0 auto; padding: 24px 16px 64px; }
h1 { margin: 0 0 4px; font-size: 24px; } h2 { margin: 32px 0 12px; font-size: 17px; }
.muted { color: var(--muted); }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin-top: 20px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; }
.card .label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
.card .value { font-size: 26px; font-weight: 650; margin-top: 4px; font-variant-numeric: tabular-nums; }
.card .sub { color: var(--muted); font-size: 12px; margin-top: 2px; }
.panel { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; overflow-x: auto; }
.grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 12px; }
table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { color: var(--muted); font-weight: 600; font-size: 12px; white-space: nowrap; }
th.sortable { cursor: pointer; user-select: none; } th.sortable:hover { color: var(--accent); }
td.num { text-align: right; white-space: nowrap; }
.badge { display: inline-block; padding: 1px 8px; border-radius: 99px; font-size: 12px; font-weight: 600; white-space: nowrap; }
.HIGH { background: var(--high-bg); color: var(--high); } .MEDIUM { background: var(--med-bg); color: var(--med); }
.LOW { background: var(--low-bg); color: var(--low); }
.neg { color: var(--high); } .pos { color: var(--ok); }
.bar { height: 10px; background: var(--bar); border-radius: 3px; min-width: 2px; }
.barrow { display: grid; grid-template-columns: 170px 1fr 40px; gap: 10px; align-items: center; margin: 6px 0; }
.filters { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
select, input { font: inherit; padding: 6px 8px; border: 1px solid var(--line); border-radius: 6px;
                background: var(--card); color: var(--text); }
input { min-width: 240px; }
.desc { max-width: 460px; } .action { color: var(--muted); font-size: 12px; margin-top: 3px; }
details { margin-top: 12px; } summary { cursor: pointer; font-weight: 600; }
code { font-size: 12px; }
.banner { margin-top: 14px; padding: 10px 14px; border-radius: 8px; border: 1px solid var(--med);
          background: var(--med-bg); color: var(--text); }
</style>
</head>
<body>
<main>
  <h1>Transaktionsabgleich</h1>
  <div class="muted" id="meta"></div>
  <div id="banner"></div>
  <div class="cards" id="cards"></div>

  <h2>Übersicht</h2>
  <div class="grid2">
    <div class="panel"><strong>Abweichungen nach Hauptbefund</strong><div id="kindbars"></div></div>
    <div class="panel"><strong>Nach Anbieter</strong><table id="providers"></table></div>
  </div>

  <h2>Abweichungen <span class="muted" id="count"></span></h2>
  <div class="panel">
    <div class="filters">
      <select id="fPrio"><option value="">Alle Prioritäten</option></select>
      <select id="fKind"><option value="">Alle Befunde</option></select>
      <select id="fProv"><option value="">Alle Anbieter</option></select>
      <input id="fText" type="search" placeholder="Suche: ID, Referenz, Text …">
    </div>
    <table id="disc"></table>
  </div>

  <h2>Zugeordnete Transaktionen <span class="muted" id="mcount"></span></h2>
  <div class="panel"><table id="matched"></table></div>

  <h2>Importprobleme</h2>
  <div class="panel" id="issues"></div>
</main>

<script type="application/json" id="data">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const STATUS = {COMPLETED:'abgeschlossen', PENDING:'ausstehend', FAILED:'fehlgeschlagen', REFUNDED:'erstattet', UNKNOWN:'unbekannt'};
const PRIO = {HIGH:'Hoch', MEDIUM:'Mittel', LOW:'Niedrig'};
const RANK = {HIGH:0, MEDIUM:1, LOW:2};
const money = (v, cur, signed) => new Intl.NumberFormat('de-DE', {style:'currency', currency:cur,
    signDisplay: signed ? 'exceptZero' : 'auto'}).format(Number(v));
const impactHtml = imp => {
  const parts = Object.entries(imp).filter(([, v]) => Number(v) !== 0)
    .map(([c, v]) => `<span class="${Number(v) < 0 ? 'neg' : 'pos'}">${esc(money(v, c, true))}</span>`);
  return parts.length ? parts.join('<br>') : '<span class="muted">±0</span>';
};
const txText = t => t ? `${esc(money(t.amount, t.currency))}<br><span class="muted">${STATUS[t.status] || t.status}</span>` : '<span class="muted">—</span>';
const worth = d => Math.max(0, ...Object.values(d.effect_defined ? d.impact : d.affected).map(v => Math.abs(Number(v))));
const sumText = imp => Object.keys(imp).length ? Object.entries(imp).map(([c, v]) => money(v, c, true)).join(' / ') : '±0';
const plain = amounts => Object.entries(amounts).map(([c, v]) => money(v, c, false)).join(' / ') || '—';
// Ohne bestimmbare Auswirkung steht hier der betroffene Betrag – bewusst NICHT als Plus/Minus-Zahl.
const effectHtml = d => d.effect_defined
  ? impactHtml(d.impact) + (d.certainty === 'PRELIMINARY' ? '<br><span class="muted">vorläufig</span>' : '')
  : `<span class="muted">nicht bestimmbar</span><br><span class="muted">betroffen: ${esc(plain(d.affected))}</span>`;

const S = D.summary;
$('meta').textContent = `Stichtag: ${D.as_of ? new Date(D.as_of).toLocaleString('de-DE', {timeZone: 'UTC'}) + ' UTC' : 'nicht gesetzt'} · Quellen: ` +
  D.sources.map(s => s.path.split(/[\\/]/).pop()).join(', ');
if (D.incomplete) {
  $('banner').innerHTML = `<div class="banner"><strong>Ergebnis unvollständig.</strong> ${esc(D.incomplete_reasons.join('; '))}. ` +
    'Zeilen mit lesbarer Referenz sind als „nicht prüfbar“ markiert; ohne lesbare Referenz sind alle „fehlt“-Befunde der Quelle vorläufig.</div>';
}

const cards = [
  ['Zuordnungsquote', (S.match_rate * 100).toFixed(1).replace('.', ',') + ' %', `${S.matched} Paare (${S.matched_exact} exakt, ${S.matched_fuzzy} unscharf)`],
  ['Abweichungen', S.discrepancies, `${S.clean_matches} Paare fehlerfrei`],
  ['Priorität hoch', S.by_priority.HIGH || 0, `${S.by_priority.MEDIUM || 0} mittel · ${S.by_priority.LOW || 0} niedrig`],
  ['Nur in Datenbank', S.unmatched_internal, 'fehlt in Abrechnung'],
  ['Nur in Abrechnung', S.unmatched_provider, 'fehlt in Datenbank'],
  ['Nicht bestimmbar', S.undefined_count, 'betroffen: ' + plain(S.undefined_affected) + ' (nicht in der Summe)'],
  ['Berechnete Nettoauswirkung', sumText(S.net_impact), 'Abrechnung − Datenbank, ohne nicht bestimmbare Befunde'],
];
$('cards').innerHTML = cards.map(([l, v, s]) =>
  `<div class="card"><div class="label">${l}</div><div class="value" style="font-size:${String(v).length > 12 ? 17 : 26}px">${esc(v)}</div><div class="sub">${esc(s)}</div></div>`).join('');

const labels = {};
D.discrepancies.forEach(d => d.kinds.forEach((k, i) => labels[k] = d.kind_labels[i]));
const kinds = Object.entries(S.by_kind);
const maxCount = Math.max(1, ...kinds.map(([, v]) => v.count));
$('kindbars').innerHTML = kinds.map(([k, v]) =>
  `<div class="barrow"><span>${esc(labels[k] || k)}</span><div class="bar" style="width:${100 * v.count / maxCount}%"></div><b>${v.count}</b></div>`).join('')
  || '<p class="muted">Keine Abweichungen.</p>';

$('providers').innerHTML = '<tr><th>Anbieter</th><th>DB</th><th>Abr.</th><th>Zugeordnet</th><th>Nur DB</th><th>Nur Abr.</th><th>Abw.</th><th>Auswirkung (berechnet)</th><th>Nicht bestimmbar</th></tr>' +
  S.providers.map(p => `<tr><td>${p.provider}</td><td class="num">${p.internal_total}</td><td class="num">${p.provider_total}</td>` +
    `<td class="num">${p.matched}</td><td class="num">${p.missing_in_provider}</td><td class="num">${p.missing_in_db}</td>` +
    `<td class="num">${p.discrepancies}</td><td class="num">${impactHtml(p.impact)}</td>` +
    `<td class="num">${p.undefined ? p.undefined + '<br><span class="muted">' + esc(plain(p.affected_undefined)) + '</span>' : '—'}</td></tr>`).join('');

// ---- Filter und Sortierung der Abweichungen ----
const fill = (id, entries) => entries.forEach(([v, t]) => $(id).insertAdjacentHTML('beforeend', `<option value="${esc(v)}">${esc(t)}</option>`));
fill('fPrio', Object.entries(PRIO));
fill('fKind', Object.entries(labels));
fill('fProv', [...new Set(D.discrepancies.map(d => d.provider))].sort().map(p => [p, 'Anbieter ' + p]));
let sort = {key: 'id', dir: 1};
const keyFns = {id: d => d.id, prio: d => RANK[d.priority], impact: d => -worth(d)};
const heads = [['id', 'Nr.'], ['prio', 'Priorität'], [null, 'Befund'], [null, 'Anbieter'], [null, 'Datenbank'], [null, 'Abrechnung'], ['impact', 'Auswirkung'], [null, 'Sicherheit'], [null, 'Beschreibung / Maßnahme']];

function renderDisc() {
  const q = $('fText').value.trim().toLowerCase();
  let rows = D.discrepancies.filter(d =>
    (!$('fPrio').value || d.priority === $('fPrio').value) &&
    (!$('fKind').value || d.kinds.includes($('fKind').value)) &&
    (!$('fProv').value || d.provider === $('fProv').value) &&
    (!q || JSON.stringify(d).toLowerCase().includes(q)));
  const f = keyFns[sort.key];
  rows.sort((a, b) => (f(a) > f(b) ? 1 : f(a) < f(b) ? -1 : a.id.localeCompare(b.id)) * sort.dir);
  $('count').textContent = `(${rows.length} von ${D.discrepancies.length})`;
  $('disc').innerHTML = '<tr>' + heads.map(([k, t]) => k ? `<th class="sortable" data-k="${k}">${t}${sort.key === k ? (sort.dir > 0 ? ' ▲' : ' ▼') : ''}</th>` : `<th>${t}</th>`).join('') + '</tr>' +
    rows.map(d => `<tr><td>${d.id}</td><td><span class="badge ${d.priority}">${PRIO[d.priority]}</span></td>` +
      `<td>${d.kind_labels.map(esc).join('<br>')}</td><td>${d.provider}</td>` +
      `<td>${d.internal ? `<code>${esc(d.internal.record_id)}</code><br>` : ''}${txText(d.internal)}</td>` +
      `<td>${d.provider_tx ? `<code>${esc(d.provider_tx.record_id)}</code><br>` : ''}${txText(d.provider_tx)}</td>` +
      `<td class="num">${effectHtml(d)}</td><td>${esc(d.certainty_label)}</td>` +
      `<td class="desc">${esc(d.description)}<div class="action">→ ${esc(d.action)}</div></td></tr>`).join('');
  document.querySelectorAll('#disc th.sortable').forEach(th => th.onclick = () => {
    sort = {key: th.dataset.k, dir: sort.key === th.dataset.k ? -sort.dir : 1}; renderDisc();
  });
}
['fPrio', 'fKind', 'fProv'].forEach(id => $(id).onchange = renderDisc);
$('fText').oninput = renderDisc;
renderDisc();

// ---- Zugeordnete Transaktionen ----
$('mcount').textContent = D.matched_total > D.matched.length
  ? `(erste ${D.matched.length} von ${D.matched_total}; alle in matched.csv)` : `(${D.matched_total})`;
$('matched').innerHTML = '<tr><th>Anbieter</th><th>DB-ID</th><th>Anbieter-ID</th><th>Zuordnung</th><th>Betrag</th><th>Status DB / Anbieter</th><th>Ergebnis</th></tr>' +
  D.matched.map(m => `<tr><td>${m.provider}</td><td><code>${esc(m.internal.record_id)}</code></td><td><code>${esc(m.provider_tx.record_id)}</code></td>` +
    `<td>${m.method === 'exact' ? 'exakt' : 'unscharf (' + Math.round(m.confidence * 100) + ' %)'}</td>` +
    `<td class="num">${esc(money(m.internal.amount, m.internal.currency))}</td>` +
    `<td>${STATUS[m.internal.status]} / ${STATUS[m.provider_tx.status]}</td>` +
    `<td>${m.has_discrepancy ? '<span class="badge MEDIUM">Abweichung</span>' : '<span class="pos">✓ in Ordnung</span>'}</td></tr>`).join('');

// ---- Importprobleme ----
$('issues').innerHTML = D.import_issues.length
  ? '<table><tr><th>Quelle</th><th>Position</th><th>Art</th><th>Meldung</th></tr>' +
    D.import_issues.map(i => `<tr><td>${esc(i.source)}</td><td>${esc(i.location)}</td><td>${i.severity === 'error' ? 'Fehler' : 'Warnung'}</td><td>${esc(i.message)}</td></tr>`).join('') + '</table>'
  : '<span class="muted">Keine.</span>';
</script>
</body>
</html>
"""


def render_html(result: ReconciliationResult) -> str:
    payload = json.dumps(result_to_dict(result, matched_limit=MAX_MATCHED_IN_HTML), ensure_ascii=False)
    payload = payload.replace("<", "\\u003c")          # verhindert vorzeitiges </script>
    return _TEMPLATE.replace("__DATA__", payload)
