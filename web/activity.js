(() => {
  const $ = id => document.getElementById(id);
  let history = [];
  const tr = (en, hi) => window.MVLanguage.get() === 'hi' ? hi : en;
  const date = value => value ? new Date(typeof value === 'number' ? value * 1000 : value).toLocaleString(undefined, {hour12:false}) : '—';
  function node(tag, text, cls) { const e = document.createElement(tag); e.textContent = text; if (cls) e.className = cls; return e; }
  function render() {
    $('jobLabel').textContent = tr('Job', 'Job'); $('levelLabel').textContent = tr('Severity', 'Level');
    $('legacyLogTitle').textContent = tr('Legacy output · old workers have no structured job IDs', 'Purane logs · old workers mein structured job ID nahi hai');
    const health = typeof state !== 'undefined' ? state?.health : null;
    const healthBox = $('queueHealth'); healthBox.replaceChildren();
    if (health) {
      const active = state.manager_active || state.worker.running;
      healthBox.append(node('strong', tr('Main queue health', 'Main queue ki health')));
      const parts = [tr('Files present', 'Files disk par') + ': ' + health.present + '/' + health.files,
        tr('Partial', 'Adhoori') + ': ' + health.partial, tr('Awaiting completion', 'Complete honi baaki') + ': ' + health.queued,
        tr('Recorded issues', 'Recorded issues') + ': ' + health.attention,
        health.stale ? tr('Offline snapshot', 'Offline snapshot') : active ? tr('Manager active', 'Manager active hai') : tr('No manager active', 'Koi manager active nahi')];
      healthBox.append(node('p', parts.join(' · ')));
      healthBox.append(node('small', tr('Size-based inventory; recorded issues may predate the current run. Main queue only; individual jobs are below.', 'Size-based count; issues purane run se ho sakte hain. Sirf main queue ki health; individual jobs neeche hain.')));
    }
    const selected = history.find(j => j.id === $('jobSelect').value);
    const details = $('jobDetails'); details.replaceChildren(); const logs = $('structuredLogs'); logs.replaceChildren();
    if (!selected) { details.append(node('p', tr('No structured jobs yet. The next job started from this updated dashboard will get an ID, timestamps and separate logs. Existing workers continue with their original output.', 'Abhi structured jobs nahi hain. Updated dashboard se agle job ko ID aur timestamps milenge. Existing worker ke purane logs neeche hain.'), 'hint')); return; }
    details.append(node('h3', selected.name)); details.append(node('p', selected.description, 'hint'));
    details.append(node('code', selected.id));
    details.append(node('p', [selected.status.toUpperCase(), 'PID ' + (selected.pid || '—'), tr('Started', 'Shuru') + ': ' + date(selected.started), tr('Ended', 'Khatam') + ': ' + date(selected.ended), Math.round(selected.elapsed_seconds) + 's', 'exit ' + (selected.exit_code ?? '—')].join(' · '), 'model-meta'));
    details.append(node('p', tr('Last activity: ', 'Last activity: ') + date(selected.last_activity) + tr(' · Running states reflect the last report; a quiet network read may be waiting for its timeout.', ' · Running state last report hai; network read timeout ka wait kar sakti hai.'), 'hint'));
    if (selected.current_file) details.append(node('p', tr('Latest file: ', 'Latest file: ') + selected.current_file));
    if (selected.progress) { const p = selected.progress; details.append(node('p', tr('Last durable checkpoint: ', 'Last safe checkpoint: ') + (p.durable_bytes/1024**2).toFixed(1) + ' MiB / ' + (p.total_bytes/1024**2).toFixed(1) + ' MiB · ' + date(p.timestamp), 'hint')); }
    for (const item of selected.logs.filter(r => $('logLevel').value === 'ALL' || r.level === $('logLevel').value)) {
      const row = node('div', '', 'log-row ' + item.level.toLowerCase());
      row.append(node('time', date(item.timestamp)), node('span', item.level, 'log-level'), node('span', item.event, 'log-event'), node('span', item.message + (item.repo ? ' · ' + item.repo : '') + (item.file ? ' · ' + item.file : ''))); logs.append(row);
    }
    if (!logs.children.length) logs.append(node('p', tr('No matching log entries.', 'Matching logs nahi hain.'), 'hint'));
  }
  async function refreshJobs() {
    try {
      const response = await fetch('/api/jobs'); if (!response.ok) throw Error('Job history unavailable');
      history = (await response.json()).jobs;
      const value = $('jobSelect').value;
      $('jobSelect').replaceChildren(...history.map(j => { const o = document.createElement('option'); o.value = j.id; o.textContent = j.name + ' · ' + j.id + ' · ' + j.status; return o; }));
      if (!history.length) { const option = document.createElement('option'); option.value = ''; option.textContent = tr('No structured jobs yet', 'Abhi structured jobs nahi hain'); $('jobSelect').append(option); }
      if (history.some(j => j.id === value)) $('jobSelect').value = value;
      render();
    } catch(e) { $('jobDetails').textContent = e.message; }
  }
  $('jobSelect').addEventListener('change', render); $('logLevel').addEventListener('change', render);
  window.addEventListener('languagechange', render); refreshJobs(); setInterval(refreshJobs, 4000);
})();
