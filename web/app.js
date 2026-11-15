const t = (text, params) => window.MVLanguage.t(text, params);
let state, signature;
const filters = {};
const $ = id => document.getElementById(id);
const bytes = n => n == null ? '—' : (n / 1024 ** 3).toFixed(2) + ' GiB';
function element(tag, text, cls) { const e = document.createElement(tag); e.textContent = t(text); if (cls) e.className = cls; return e; }
const dimensions = [
  ['tags', 'By category / behavior'], ['publisher', 'By publisher'],
  ['download_status', 'By download status'], ['format', 'By format'], ['license', 'By license']
];
function values(model, key) { return key === 'tags' ? model.tags : [model[key] || 'Unknown']; }
function renderSegments() {
  const target = $('segments'); target.replaceChildren();
  for (const [key, title] of dimensions) {
    const group = element('div', '', 'segment'); group.append(element('h3', title));
    const counts = new Map();
    for (const m of state.items) for (const v of values(m, key)) counts.set(v, (counts.get(v) || 0) + 1);
    const list = element('div', '', 'chips');
    for (const [value, count] of [...counts].sort((a,b) => b[1] - a[1] || a[0].localeCompare(b[0]))) {
      const button = element('button', t(value) + ' · ' + count, 'chip ' + (filters[key] === value ? 'active' : ''));
      button.setAttribute('aria-pressed', String(filters[key] === value));
      button.addEventListener('click', () => { if (filters[key] === value) delete filters[key]; else filters[key] = value; renderSegments(); renderQueue(); });
      list.append(button);
    }
    group.append(list); target.append(group);
  }
}
function renderQueue() {
  const target = $('queue');
  const opened = new Set([...target.querySelectorAll('details[open]')].map(e => e.dataset.repo));
  target.replaceChildren();
  const query = $('search').value.toLowerCase();
  const complete = m => m.files.length > 0 && m.files.every(f => f.present);
  const includeCompleted = $('showCompleted').checked;
  $('showCompletedLabel').textContent = window.MVLanguage.get() === 'hi' ? 'Queue mein completed models bhi dikhao' : 'Show completed models in queue';
  const shown = state.items.filter(m => (includeCompleted || !complete(m)) && (m.repo + ' ' + m.category + ' ' + m.tags.join(' ')).toLowerCase().includes(query)
      && Object.entries(filters).every(([key, value]) => values(m, key).includes(value)));
  const hiddenCompleted = includeCompleted ? 0 : state.items.filter(complete).length;
  $('queueCount').textContent = t('Showing {shown} of {total} models', {shown: shown.length, total: state.items.length}) + (hiddenCompleted ? (window.MVLanguage.get() === 'hi' ? ' · ' + hiddenCompleted + ' completed library mein hain' : ' · ' + hiddenCompleted + ' completed models in library') : '');
  $('filterSummary').textContent = Object.entries(filters).map(([key, value]) => t(dimensions.find(d => d[0] === key)[1]) + ': ' + t(value)).join(' · ') || t('All segments');
  for (const model of shown) {
    const card = element('article', '', 'model-card');
    const head = element('div', '', 'model-head');
    head.append(element('h3', model.repo));
    const badges = element('div', '', 'badges');
    for (const tag of model.tags) {
      const badge = element('button', tag, 'badge ' + tag.toLowerCase());
      badge.title = t('Filter by {tag}', {tag});
      badge.addEventListener('click', () => { filters.tags = tag; renderSegments(); renderQueue(); }); badges.append(badge);
    }
    head.append(badges); card.append(head);
    const size = model.files.reduce((n,f) => n + f.size, 0);
    card.append(element('p', model.publisher + ' · ' + model.format + ' · ' + t(model.download_status) + ' · ' + bytes(size) + ' · ' + t('{count} files', {count: model.files.length}), 'model-meta'));
    const detail = element('details', '', 'model'); detail.dataset.repo = model.repo; detail.open = opened.has(model.repo);
    detail.append(element('summary', 'View files, pinned revision & license'));
    detail.append(element('p', t('Revision') + ' ' + model.revision + ' · ' + t('License') + ': ' + (model.license || t('See model card')), 'hint'));
    for (const file of model.files) {
      const row = element('div', '', 'file');
      row.append(element('div', file.name));
      row.append(element('small', bytes(file.size) + ' · ' + t(file.status) + (file.durable_bytes ? ' · ' + bytes(file.durable_bytes) + ' ' + t('durable') : '')));
      if (file.error) row.append(element('p', file.error, 'error'));
      const progress = document.createElement('progress'); progress.max = file.size || 1; progress.value = file.present ? file.size : file.durable_bytes; progress.setAttribute('aria-label', file.name + ' bytes present or durable'); row.append(progress); detail.append(row);
    }
    card.append(detail); target.append(card);
  }
  if (!target.children.length) target.append(element('p', (!includeCompleted && state.items.every(complete) ? (window.MVLanguage.get() === 'hi' ? 'Queue complete hai. Saare downloaded models library mein dekho.' : 'Queue complete. All downloaded models are in your library.') : 'No models match. Clear filters to see the full queue.')));
}
function buttons() {
  const running = state?.worker.running;
  const available = state?.ready && !state?.cached;
  const hasFiles = state?.items.some(m => m.files.some(f => f.present));
  $('start').disabled = !available || !$('review').checked || running || state?.manager_active;
  $('verify').disabled = !available || !hasFiles || !$('review').checked || running || state?.manager_active;
  $('verifyReason').textContent = !hasFiles ? t('No downloaded files yet — verification becomes available after files are downloaded.') : t('Verification checks the full queue and reports missing or corrupt files.');
  $('verify').title = !hasFiles ? t('No downloaded files to verify') : t('Verify downloaded files; report missing files');
  $('stop').disabled = !running;
}
function renderStatus() {
  $('connection').textContent = state.ready ? t('● Drive connected') : t('○ Needs attention');
  $('notice').textContent = state.cached ? t('Drive unavailable. Showing the last saved queue from SQLite; download controls are disabled. ') + (state.error || '') : state.error || t('Queue ready for review. Downloads start only when you choose Start / Resume.');
  $('notice').className = state.error ? 'error notice' : 'notice';
  $('models').textContent = t('{count} models', {count: state.items.length}); $('size').textContent = bytes(state.total_bytes);
  $('present').textContent = bytes(state.completed_bytes); $('free').textContent = bytes(state.free_bytes);
  $('drive').textContent = (state.volume || t('No drive configured')) + ' · ' + t('{count} GiB reserved', {count: state.reserve_gib});
  $('worker').textContent = state.manager_active && !state.worker.running ? (window.MVLanguage.get() === 'hi' ? 'Doosra download worker active hai' : 'Another manager is active') : state.worker.running ? t('Running: ') + state.worker.action : state.worker.exit_code == null ? t('Idle') : t('Exited: ') + state.worker.exit_code;
  $('catalogCount').textContent = state.catalog.length;
  const catalog = $('catalog'); catalog.replaceChildren();
  for (const row of state.catalog) catalog.append(element('p', row.repo + ' · ' + row.category + ' · ' + (row.enabled ? t('enabled') : t('disabled'))));
  renderSegments(); renderQueue(); buttons();
  window.dispatchEvent(new Event('vaultstatus'));
}
async function refresh() {
  try {
    const response = await fetch('/api/status'); if (!response.ok) throw Error(t('Status unavailable'));
    state = await response.json();
    if (signature !== state.signature) $('review').checked = false;
    signature = state.signature;
    renderStatus();
    const log = await fetch('/api/log'); if (log.ok) $('log').textContent = (await log.json()).text;
  } catch (error) { $('connection').textContent = t('Disconnected'); $('notice').textContent = error.message; for (const id of ['start', 'verify', 'stop']) $(id).disabled = true; }
}
async function action(name) {
  for (const id of ['start', 'verify', 'stop']) $(id).disabled = true;
  try {
    const response = await fetch('/api/' + name, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': state.csrf}, body: JSON.stringify({signature, reviewed: $('review').checked})});
    const result = await response.json(); if (!response.ok) throw Error(result.error);
    await refresh();
  } catch (error) { $('notice').textContent = error.message; buttons(); }
}
$('clearFilters').addEventListener('click', () => { for (const k of Object.keys(filters)) delete filters[k]; $('search').value = ''; renderSegments(); renderQueue(); });
$('showCompleted').addEventListener('change', renderQueue);
$('review').addEventListener('change', buttons); $('search').addEventListener('input', renderQueue);
for (const id of ['start', 'verify', 'stop']) $(id).addEventListener('click', () => action(id));
refresh(); setInterval(refresh, 4000);

window.addEventListener('languagechange', () => { if (state) renderStatus(); });
