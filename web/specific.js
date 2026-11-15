(() => {
  const $ = id => document.getElementById(id);
  const text = {
    revision: ['Revision', 'Version'], license: ['License', 'License'], gated: ['Gated access', 'Access approval chahiye'], selected: ['Selected', 'Selected size'], free: ['Free', 'Khali jagah'], reserve: ['Reserve', 'Reserve'], card: ['See upstream model card', 'Upstream model card dekho'],
    title: ['Download a specific model', 'Specific model download karo'],
    intro: ['Paste a Hugging Face model repository. Preview exact files first, then download only this model without changing your main queue.', 'Hugging Face repo paste karo. Pehle exact files dekho, phir sirf yeh model download karo. Main queue nahi badlegi.'],
    repo: ['Repository URL or owner/repo', 'Repo ka URL ya owner/repo'], format: ['Format', 'Format'],
    quant: ['Quantization (GGUF)', 'Quantization (GGUF)'], category: ['Category (your label)', 'Category (aapka label)'],
    preview: ['Preview files & size', 'Files aur size preview karo'],
    review: ['I reviewed these exact files, license, revision and storage requirements.', 'Maine yeh exact files, license, revision aur storage requirement review kar li hai.'],
    start: ['Download only this model', 'Sirf yeh model download karo'],
    note: ['Uses the same drive guards, space reserve, exclusive lock and recovery checkpoints. Gated repositories need access and an HF token configured through the CLI. Standard native downloads support safetensors; custom .bin/adapters need manual setup.', 'Same drive guards, reserve, lock aur checkpoints use honge. Gated repos ke liye access aur CLI se HF token chahiye. Native option safetensors ke liye hai; custom .bin/adapters manually configure karo.'],
    loading: ['Fetching metadata only… No model download has started.', 'Sirf metadata fetch ho raha hai… model download start nahi hua.'],
    started: ['Single-model worker started. See Worker activity below; Stop safely stops this worker. Main queue is unchanged.', 'Single-model worker start ho gaya. Worker activity neeche dekho; Stop safely se rok sakte ho. Main queue nahi badli.'],
    expired: ['Preview again after changing inputs.', 'Inputs badalne ke baad dobara preview karo.']
  };
  const tr = key => text[key][window.MVLanguage.get() === 'hi' ? 1 : 0];
  let preview, busy = false;
  const gib = n => (n / 1024 ** 3).toFixed(2) + ' GiB';
  function labels() { document.querySelectorAll('[data-specific]').forEach(e => e.textContent = tr(e.dataset.specific)); }
  function invalidate() { preview = null; $('specificReview').checked = false; $('specificStart').disabled = true; $('specificConfirm').hidden = true; $('specificResult').hidden = true; }
  async function post(path, payload) {
    const response = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': state.csrf}, body: JSON.stringify(payload)});
    const data = await response.json(); if (!response.ok) throw Error(data.error || 'Request failed'); return data;
  }
  function renderPreview() {
    if (!preview) return;
    const box = $('specificResult'); box.replaceChildren(); box.hidden = false;
    const item = preview.plan.items[0];
    window.renderModelMatches(box,preview.match_check);
    for (const value of [item.repo, tr('revision') + ': ' + item.revision, tr('license') + ': ' + (item.license || tr('card')) + ' · ' + tr('gated') + ': ' + Boolean(item.gated),
      tr('selected') + ': ' + gib(preview.plan.total_bytes) + ' · ' + tr('free') + ': ' + gib(preview.free_bytes) + ' · ' + tr('reserve') + ': ' + preview.reserve_gib + ' GiB']) {
      const p = document.createElement('p'); p.textContent = value; box.append(p);
    }
    const link = document.createElement('a'); link.href = 'https://huggingface.co/' + item.repo; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.textContent = window.MVLanguage.get() === 'hi' ? 'Model card aur license dekho' : 'Read model card & license'; box.append(link);
    const list = document.createElement('ul');
    for (const file of item.files) { const li = document.createElement('li'); li.textContent = file.name + ' · ' + gib(file.size); list.append(li); } box.append(list);
    if (preview.free_bytes < preview.plan.total_bytes + preview.reserve_gib * 1024 ** 3) {
      const warning = document.createElement('p'); warning.className = 'error'; warning.textContent = window.MVLanguage.get() === 'hi' ? 'Full selection aur reserve ke liye space kam ho sakti hai. Worker remaining bytes dobara check karega.' : 'Space may be insufficient for the full selection plus reserve. The worker rechecks remaining bytes.'; box.append(warning);
    }
  }
  $('specificForm').addEventListener('submit', async event => {
    event.preventDefault(); if (busy || !state) return; busy = true; invalidate(); $('specificPreview').disabled = true; $('specificMessage').textContent = tr('loading');
    try {
      preview = await post('/api/model/preview', {repo: $('specificRepo').value, format: $('specificFormat').value, quant: $('specificQuant').value, category: $('specificCategory').value});
      renderPreview(); $('specificConfirm').hidden = false; $('specificMessage').textContent = '';
    } catch (e) { $('specificMessage').textContent = e.message; }
    finally { busy = false; $('specificPreview').disabled = false; }
  });
  for (const id of ['specificRepo', 'specificFormat', 'specificQuant', 'specificCategory']) $(id).addEventListener('input', () => { invalidate(); $('specificMessage').textContent = tr('expired'); $('specificQuant').disabled = $('specificFormat').value !== 'gguf'; });
  $('specificReview').addEventListener('change', () => $('specificStart').disabled = !preview || !$('specificReview').checked || busy);
  $('specificStart').addEventListener('click', async () => {
    if (!preview || busy || !$('specificReview').checked) return; busy = true; $('specificStart').disabled = true;
    try { await post('/api/model/start', {preview: preview.preview, reviewed: true}); $('specificMessage').textContent = tr('started'); invalidate(); await refresh(); }
    catch (e) { $('specificMessage').textContent = e.message; }
    finally { busy = false; $('specificStart').disabled = !preview || !$('specificReview').checked; }
  });
  window.addEventListener('languagechange', () => { labels(); renderPreview(); }); labels();
})();
