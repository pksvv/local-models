(() => {
  const $=id=>document.getElementById(id), tr=(en,hi)=>window.MVLanguage.get()==='hi'?hi:en;
  let research={},selected=new Set(),fingerprint='';
  const node=(tag,text)=>{const e=document.createElement(tag);e.textContent=text;return e;};
  let tipIndex = Math.floor(Math.random()*7);
  const tips = [
    ['Abliterated describes a refusal-reduction modification—not a guarantee of better reasoning.', 'Abliterated refusal kam karne ki modification hai—better reasoning ki guarantee nahi.'],
    ['A model file is only part of the story. Tokenizers, configs and licenses preserve its context.', 'Model file ke saath tokenizer, config aur license bhi uska context preserve karte hain.'],
    ['Your archive is a time capsule: pinned revisions keep a specific release within reach.', 'Aapka archive time capsule hai: pinned revision se exact release preserve hoti hai.'],
    ['5 TB is a destination. Small, reviewed batches are how a useful library grows.', '5 TB ek target hai. Chhote reviewed batches se useful library banti hai.'],
    ['Uncensored and abliterated describe behavior-related labels, not accuracy ratings.', 'Uncensored aur abliterated behavior labels hain, accuracy ratings nahi.'],
    ['Quantization trades precision for a smaller footprint. Runtime and RAM still matter.', 'Quantization footprint kam karti hai. Runtime aur RAM phir bhi matter karte hain.'],
    ['A checkpoint saves progress. A checksum checks integrity. A second copy is your backup.', 'Checkpoint progress bachata hai. Checksum integrity check karta hai. Second copy backup hai.']
  ];
  function live() {
    const status=research.status||'idle',running=status==='running',validation=research.stage==='validation';
    const seconds=research.started?Math.max(0,Math.floor(((research.finished||Date.now()/1000)-research.started))):0;
    $('researchElapsed').textContent=research.started ? String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0')+' '+tr('elapsed','elapsed') : status==='completed' ? tr('Duration unavailable','Duration available nahi') : '00:00';
    $('researchStage').textContent=status==='completed'?tr('Research complete · ready for review','Research complete · review karo'):running?(validation?tr('Validating pinned model files','Pinned model files validate ho rahi hain'):tr('Searching releases & model cards','Releases aur model cards search ho rahe hain')):status==='failed'||status==='interrupted'?tr('Research needs attention','Research ko attention chahiye'):tr('Your next discovery starts here','Agli discovery yahan se shuru hoti hai');
    const bar=$('researchProgress');
    if(status==='completed'){bar.max=1;bar.value=1;}
    else if(validation && research.total){bar.max=research.total;bar.value=research.checked||0;}
    else if(running){bar.removeAttribute('value');bar.max=1;}
    else{bar.max=1;bar.value=0;}
    $('researchCounter').textContent=validation?`${research.checked||0}/${research.total||'?'} `+tr('candidates checked','candidates check hue'):status==='completed'?`${(research.candidates||[]).filter(c=>c.status==='validated').length}/${(research.candidates||[]).length} `+tr('candidates validated','candidates validated'):running?tr('Live discovery · total not known yet','Live discovery · total abhi unknown'):tr('No downloads started by research','Research se download start nahi hota');
    $('researchMode').textContent=running?tr('METADATA ONLY · NO WEIGHT TRANSFERS','SIRF METADATA · MODEL TRANSFER NAHI'):tr('REVIEW BEFORE DOWNLOAD','DOWNLOAD SE PEHLE REVIEW');
    const steps=$('researchSteps');steps.replaceChildren();
    const active=status==='completed'?3:validation?2:running?1:0;
    [tr('Discover','Discover'),tr('Cross-check sources','Sources check'),tr('Validate files','Files validate'),tr('Review & queue','Review aur queue')].forEach((label,i)=>{const step=node('span',(i<active?'✓ ':i+1+'. ')+label);step.className=i<active?'done':i===active?'current':'';steps.append(step);});
    $('researchActivity').textContent=research.current_repo&&validation?tr('Checking: ','Check ho raha hai: ')+research.current_repo:running&&research.activity?.length?research.activity[research.activity.length-1]:running?tr('The agent is checking primary sources. Search time depends on available evidence; no estimated percentage is invented.','Agent primary sources check kar raha hai. Evidence ke hisaab se time lagega; fake percentage nahi dikhayi jaati.'):tr('Pinned files. Clear provenance. A library you can keep.','Pinned files. Clear sources. Aapki apni library.');
    $('researchTipLabel').textContent=tr('WHILE YOU EXPLORE · VAULT NOTES','RESEARCH KE SAATH · VAULT NOTES');
    $('researchTip').textContent=tips[tipIndex][window.MVLanguage.get()==='hi'?1:0];
    $('researchLive').classList.toggle('is-running',running);
  }
  async function post(path,data){const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrf},body:JSON.stringify(data)});const result=await response.json();if(!response.ok)throw Error(result.error);return result;}
  function controls(){ $('researchEnqueue').disabled=!selected.size||!$('researchReview').checked||research.status!=='completed'||state?.manager_active; }
  function render(){
    $('researchTitle').textContent=tr('Research & refresh queue','Research aur queue refresh');$('researchStart').textContent=tr('Research latest models','Latest models research karo');
    $('researchIntro').textContent=tr('Codex CLI uses live web search for release news, then validates files on Hugging Face. Results are candidates, not a quality benchmark. Select a small batch, review it, and append without starting downloads. A 5 TB+ archive is a long-term goal; current free space and reserve still apply. Requires installed, signed-in Codex CLI and may consume its usage allowance.','Codex CLI live news search karega, phir Hugging Face files validate hongi. Candidates quality benchmark nahi hain. Chhota batch review karke queue mein add karo; download auto-start nahi hoga. 5 TB+ long-term target hai; actual free space aur reserve apply honge. Signed-in Codex CLI chahiye; usage allowance lag sakta hai.');
    $('researchQueryLabel').textContent=tr('Research phrase or model name (optional)','Research phrase ya model name (optional)');
    $('researchQuery').placeholder=tr('uncensored, abliterated coding models, Qwen','uncensored, abliterated coding models, Qwen');
    $('budgetLabel').textContent=tr('Maximum new batch (GiB)','Naya batch limit (GiB)');$('researchReviewText').textContent=tr('I reviewed selected models, exact files, licenses and batch size.','Maine selected models, exact files, licenses aur batch size review kiya.');$('researchEnqueue').textContent=tr('Add selected to queue','Selected queue mein add karo');
    $('researchStart').disabled=research.status==='running';$('researchStatus').textContent=[research.status||'idle',research.query?tr('Research topic: ','Research topic: ')+research.query:'',research.summary||'',research.error||''].filter(Boolean).join(' · ');
    const box=$('researchCandidates');box.replaceChildren();
    (research.candidates||[]).forEach((item,index)=>{
      const card=node('article','');card.className='model-card';const label=node('label','');const check=document.createElement('input');check.type='checkbox';check.checked=selected.has(index);check.disabled=item.status!=='validated'||research.status!=='completed';check.addEventListener('change',()=>{if(check.checked)selected.add(index);else selected.delete(index);$('researchReview').checked=false;controls();});label.append(check,node('strong',' '+item.repo));card.append(label,node('p',item.reason));
      const source=document.createElement('a');source.href=item.source;source.target='_blank';source.rel='noopener noreferrer';source.textContent=tr('Release / source','Release / source')+' · '+item.published;card.append(source);
      if(item.plan){window.renderModelMatches(card,item.match_check);const m=item.plan.items[0];card.append(node('p',m.category+' · '+m.format+' · '+(item.plan.total_bytes/1024**3).toFixed(2)+' GiB · '+(m.license||'License: see model card')));const details=node('details','');details.append(node('summary',tr('Review pinned files','Pinned files review karo')),node('p',m.revision));for(const f of m.files)details.append(node('p',f.name+' · '+(f.size/1024**2).toFixed(2)+' MiB'));card.append(details);}else card.append(node('p',item.error||item.status));box.append(card);
    });controls();live();
  }
  async function refreshResearch(){try{const response=await fetch('/api/research');if(!response.ok)throw Error('Research status unavailable');const value=await response.json();const next=JSON.stringify(value);if(next!==fingerprint){selected.clear();$('researchReview').checked=false;fingerprint=next;research=value;render();}controls();}catch(e){$('researchStatus').textContent=e.message;}}
  $('researchStart').addEventListener('click',async()=>{try{await post('/api/research/start',{query:$('researchQuery').value});await refreshResearch();}catch(e){$('researchStatus').textContent=e.message;}});
  $('researchEnqueue').addEventListener('click',async()=>{try{$('researchEnqueue').disabled=true;const result=await post('/api/research/enqueue',{indices:[...selected],signature:state.signature,budget_gib:Number($('researchBudget').value),reviewed:$('researchReview').checked});$('researchStatus').textContent=tr('Added models: ','Models add hue: ')+result.added+tr('. No downloads started. Review the updated full queue before Start.','. Download start nahi hua. Start se pehle poori updated queue review karo.');$('researchReview').checked=false;selected.clear();await refresh();controls();}catch(e){$('researchStatus').textContent=e.message;controls();}});
  $('researchReview').addEventListener('change',controls);$('researchBudget').addEventListener('input',()=>{$('researchReview').checked=false;controls();});window.addEventListener('languagechange',render);window.addEventListener('vaultstatus',controls);setInterval(live,1000);setInterval(()=>{tipIndex=(tipIndex+1+Math.floor(Math.random()*(tips.length-1)))%tips.length;live();},9000);render();refreshResearch();setInterval(refreshResearch,5000);
})();
