// Section disclosure keeps forms, live polling and deep links intact.
(() => {
  const configurations = [
    ['modelLibrary', '#libraryTitle', '01', 'LIBRARY'],
    ['researchPanel', '#researchTitle', '02', 'DISCOVER'],
    ['batchPanel', '#batchTitle', '03', 'ADD TO QUEUE'],
    ['specific', '[data-specific="title"]', '04', 'SINGLE MODEL'],
    [null, 'h2', '05', 'EXPLORE', '[aria-label="Queue segmentation"]'],
    [null, '#downloadQueue', '06', 'DOWNLOADS'],
    [null, '#worker', '07', 'ACTIVITY']
  ];
  const sections = [];
  for (const [id, selector, number, caption, container] of configurations) {
    const section = id ? document.getElementById(id) : container ? document.querySelector(container) : document.querySelector(selector)?.closest('section');
    if (!section) continue;
    const heading = section.querySelector('h2');
    if (!heading) continue;
    const key = id || 'section-' + number;
    if (!section.id) section.id = key;
    const button = document.createElement('button'); button.type = 'button'; button.className = 'section-disclosure';
    const index = document.createElement('span'); index.className = 'section-index'; index.textContent = number;
    const title = document.createElement('span'); title.className = 'section-title'; title.textContent = heading.textContent;
    const meta = document.createElement('span'); meta.className = 'section-caption'; meta.textContent = caption;
    const arrow = document.createElement('span'); arrow.className = 'section-chevron'; arrow.textContent = '⌄'; arrow.setAttribute('aria-hidden', 'true');
    button.append(index, title, meta, arrow);
    const body = document.createElement('div'); body.className = 'section-body'; body.id = key + '-content';
    while (section.firstChild) body.append(section.firstChild);
    section.append(button, body); section.classList.add('collapsible-section');
    heading.classList.add('section-original-heading');
    button.setAttribute('aria-controls', body.id);
    function setOpen(value, save=false) {
      body.hidden = !value; button.setAttribute('aria-expanded', String(value));
      section.classList.toggle('section-collapsed', !value);
      if (save) try { localStorage.setItem('model-vault-section-' + key, value ? 'open' : 'closed'); } catch (_) {}
    }
    let initial = ['modelLibrary','researchPanel','section-06','section-07'].includes(key);
    try { const saved=localStorage.getItem('model-vault-section-' + key); if(saved) initial=saved==='open'; } catch (_) {}
    setOpen(initial);
    button.addEventListener('click', () => setOpen(body.hidden, true));
    // Existing language scripts update original headings; mirror their titles without replacing controls.
    new MutationObserver(() => { title.textContent = heading.textContent; }).observe(heading, {childList:true,subtree:true,characterData:true});
    sections.push({section,body,setOpen});
  }
  function openHash() {
    const hash=decodeURIComponent(location.hash.slice(1)); if(!hash)return;
    const target=document.getElementById(hash); if(!target)return;
    for(const item of sections) if(item.section===target || item.section.contains(target)) item.setOpen(true);
    requestAnimationFrame(()=>target.scrollIntoView({block:'start'}));
  }
  window.addEventListener('hashchange',openHash);
  // Clicking the current hash must also reopen a section that was manually collapsed.
  document.addEventListener('click',event=>{const link=event.target.closest('a[href*="#"]');if(link){const url=new URL(link.href,location.href);if(url.origin===location.origin&&url.pathname===location.pathname&&url.hash===location.hash)setTimeout(openHash,0);}});
  openHash();
})();
