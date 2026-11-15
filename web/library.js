(() => {
  const $ = id => document.getElementById(id);
  const tr = (en, hi) => window.MVLanguage.get()==='hi' ? hi : en;
  let library = {available:false,models:[]};
  function el(tag,text,cls) {const e=document.createElement(tag);e.textContent=text;if(cls)e.className=cls;return e;}
  function render() {
    $('libraryTitle').textContent=tr('Downloaded models','Aapke downloaded models');
    $('queueLink').textContent=tr('View queue','Queue dekho');
    $('librarySearchLabel').textContent=tr('Search your downloaded library','Downloaded library mein search karo');
    $('librarySearch').placeholder=tr('Model name or category','Model naam ya category');
    const box=$('completionSummary');box.replaceChildren();
    if (typeof state!=='undefined' && state) {
      const all=state.items;
      const complete=all.filter(m=>m.files.length && m.files.every(f=>f.present)).length;
      const partial=all.filter(m=>!m.files.every(f=>f.present) && m.files.some(f=>f.present||f.durable_bytes)).length;
      const pending=all.length-complete-partial;
      for(const [label,count,cls] of [[tr('Completed in main queue','Main queue completed'),complete,'complete'],[tr('Partially downloaded','Adhoore downloads'),partial,'partial'],[tr('Not started','Abhi shuru nahi hue'),pending,'pending'],[tr('In downloaded library','Downloaded library mein'),library.models.length,'complete']]) {
        const card=el('div','', 'completion-card '+cls);card.append(el('strong',count),el('span',label));box.append(card);
      }
    }
    $('libraryNote').textContent=library.available ? tr('Complete file selections found on your drive, including saved single-model plans and previous queue snapshots. Previously verified is a historical checksum result; this view checks file sizes, not fresh hashes. Unknown folders without saved plans are not inventoried.','Drive par complete file selections, single-model plans aur purane queue snapshots bhi. Previously verified purana checksum result hai; yahan fresh hashes nahi, sizes check hoti hain. Saved plan ke bina unknown folders include nahi hain.') : tr('Drive unavailable. Downloaded library cannot be checked live.','Drive unavailable hai. Library live check nahi ho sakti.');
    const target=$('libraryItems');target.replaceChildren();
    const q=$('librarySearch').value.toLowerCase();
    const shown=library.models.filter(m=>(m.repo+' '+m.category).toLowerCase().includes(q));
    for(const m of shown) {
      const card=el('article','', 'library-card');
      const head=el('div','', 'model-head');head.append(el('h3',m.repo),el('span',tr('✓ Download complete','✓ Download complete'),'complete-badge'));card.append(head);
      card.append(el('p',m.category+' · '+(m.size/1024**3).toFixed(2)+' GiB · '+m.files+' '+tr('files','files'),'model-meta'));
      card.append(el('p',m.verification==='Previously verified'?tr('✓ Previously checksum-verified','✓ Pehle checksum-verified'):tr('Verification pending','Verification pending'),'verification-label'));
      card.append(el('p',tr('Revision: ','Version: ')+m.revision,'hint'));
      if(m.last_checked) card.append(el('p',tr('Last recorded file check: ','Last recorded file check: ')+new Date(m.last_checked*1000).toLocaleString(),'hint'));
      const location=el('details','');location.append(el('summary',tr('Saved location','Saved location')),el('code',m.location));card.append(location);
      target.append(card);
    }
    if(!shown.length) target.append(el('p',library.models.length?tr('No matching downloaded models.','Matching downloaded models nahi mile.'):tr('No complete models found yet. Completed downloads will appear here automatically.','Abhi complete model nahi mila. Download complete hote hi yahan dikhega.'),'hint'));
  }
  async function refreshLibrary(){try{const response=await fetch('/api/library');if(!response.ok)throw Error('Library unavailable');library=await response.json();render();}catch(e){$('libraryNote').textContent=e.message;}}
  $('librarySearch').addEventListener('input',render);window.addEventListener('languagechange',render);window.addEventListener('vaultstatus',render);refreshLibrary();setInterval(refreshLibrary,5000);
})();
