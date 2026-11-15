(() => {
  const $=id=>document.getElementById(id),tr=(en,hi)=>window.MVLanguage.get()==='hi'?hi:en;
  const node=(tag,text)=>{const e=document.createElement(tag);e.textContent=text;return e;};
  let batch=null,selected=new Set(),categories={},busy=false;
  const cat=['General','Abliterated','Uncensored','Coding','Reasoning','Vision','Embedding','Reranking','Speech'];
  async function post(path,data){const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrf},body:JSON.stringify(data)});const result=await response.json();if(!response.ok)throw Error(result.error);return result;}
  function controls(){
    $('batchAdd').disabled=busy||!batch||!selected.size||!$('batchReview').checked||state?.manager_active;
    const size=batch?batch.rows.reduce((sum,row,i)=>sum+(selected.has(i)?row.plan.total_bytes:0),0):0;
    $('batchTotal').textContent=selected.size+tr(' selected · ',' selected · ')+(size/1024**3).toFixed(2)+' GiB'+(state?.manager_active?tr(' · Stop the active worker before adding to queue.',' · Queue mein add karne se pehle active worker stop karo.'):'');
  }
  function labels(){
    $('batchTitle').textContent=tr('Add models from links','Links se models queue mein add karo');
    $('batchIntro').textContent=tr('Paste up to 10 exact repository links. No web research needed. Preview files and sizes, select models and category labels, then append to your main queue. Auto can select large native weights: review each format and size. Downloads never start here.','10 tak exact repo links paste karo. Research ki zarurat nahi. Files/sizes preview karo, models aur categories choose karke main queue mein add karo. Auto bade native weights choose kar sakta hai: format aur size review karo. Yahan se downloads start nahi hote.');
    $('batchLinksLabel').textContent=tr('Repository URLs or owner/repo — one per line','Repo URL ya owner/repo — har line par ek');$('batchFormatLabel').textContent=tr('Format','Format');$('batchBudgetLabel').textContent=tr('New batch limit (GiB)','Naya batch limit (GiB)');$('batchPreview').textContent=tr('Preview links','Links preview karo');$('batchReviewText').textContent=tr('I reviewed selected models, exact files, formats, licenses and sizes.','Maine selected models, exact files, formats, licenses aur sizes review kiye.');$('batchAdd').textContent=tr('Add selected to queue','Selected queue mein add karo');controls();
  }
  function reset(){batch=null;selected.clear();categories={};$('batchReview').checked=false;$('batchResults').replaceChildren();$('batchConfirmation').hidden=true;controls();}
  function render(){const box=$('batchResults');box.replaceChildren();batch.rows.forEach((row,index)=>{
    const card=node('article','');card.className='model-card';const check=document.createElement('input');check.type='checkbox';check.checked=selected.has(index);check.disabled=row.status!=='validated';check.addEventListener('change',()=>{if(check.checked)selected.add(index);else selected.delete(index);$('batchReview').checked=false;controls();});const label=node('label','');label.append(check,node('strong',' '+row.repo));card.append(label);
    if(row.plan){const m=row.plan.items[0];card.append(node('p',row.format.toUpperCase()+' · '+(row.plan.total_bytes/1024**3).toFixed(2)+' GiB · License: '+(m.license||'See model card')+' · Gated: '+Boolean(m.gated)));
      const select=document.createElement('select');select.setAttribute('aria-label','Category for '+row.repo);for(const c of cat){const option=node('option',c);option.value=c;select.append(option);}select.value=categories[index]||'General';select.addEventListener('change',()=>{categories[index]=select.value;$('batchReview').checked=false;controls();});card.append(node('span',tr('Category (choose your label): ','Category (aap choose karo): ')),select);
      const details=node('details','');details.append(node('summary',tr('Exact files & revision','Exact files aur revision')),node('p',m.revision));for(const f of m.files)details.append(node('p',f.name+' · '+(f.size/1024**2).toFixed(2)+' MiB'));card.append(details);
      const source=node('a',tr('Read model card / license','Model card / license dekho'));source.href='https://huggingface.co/'+m.repo;source.target='_blank';source.rel='noopener noreferrer';card.append(source);
    }else card.append(node('p',row.error));box.append(card);
  });$('batchConfirmation').hidden=false;controls();}
  $('batchForm').addEventListener('submit',async e=>{e.preventDefault();if(busy||!state)return;reset();busy=true;$('batchPreview').disabled=true;$('batchMessage').textContent=tr('Fetching metadata only…','Sirf metadata fetch ho raha hai…');try{batch=await post('/api/batch/preview',{links:$('batchLinks').value,format:$('batchFormat').value,quant:$('batchQuant').value});$('batchMessage').textContent=tr('Preview ready. Select the models you want to queue.','Preview ready. Queue ke liye models select karo.');render();}catch(e){$('batchMessage').textContent=e.message;}finally{busy=false;$('batchPreview').disabled=false;controls();}});
  for(const id of ['batchLinks','batchFormat','batchQuant'])$(id).addEventListener('input',reset);
  $('batchBudget').addEventListener('input',()=>{$('batchReview').checked=false;controls();});$('batchReview').addEventListener('change',controls);
  $('batchAdd').addEventListener('click',async()=>{if(busy)return;busy=true;controls();try{const result=await post('/api/batch/enqueue',{batch:batch.batch,indices:[...selected],categories,signature:state.signature,budget_gib:Number($('batchBudget').value),reviewed:$('batchReview').checked});reset();$('batchMessage').textContent=tr('Models added: ','Models add hue: ')+result.added+tr('. No downloads started.','. Downloads start nahi hue.');await refresh();}catch(e){$('batchMessage').textContent=e.message;}finally{busy=false;controls();}});
  window.addEventListener('languagechange',labels);window.addEventListener('vaultstatus',controls);labels();
})();
