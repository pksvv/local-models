// Shared advisory match cards: no automatic skipping of similar models.
window.renderModelMatches = (parent, check) => {
  const hi=window.MVLanguage.get()==='hi';
  const node=(tag,text)=>{const e=document.createElement(tag);e.textContent=text;return e;};
  if(!check)return;
  const box=node('aside','');box.className='model-matches';
  if(!check.available){box.append(node('p',hi?'Duplicate check available nahi hai.':'Duplicate check unavailable.'));parent.append(box);return;}
  if(!check.matches.length){box.append(node('p',hi?'Known library/queue mein match nahi mila.':'No matches found in known library or queue.'));parent.append(box);return;}
  box.append(node('strong',hi?'Add karne se pehle compare karo':'Compare before adding'));
  for(const match of check.matches){
    const row=node('div','');row.className='match-row';
    const label=match.kind==='already_downloaded'?(hi?'Already downloaded · size match':'Already downloaded · size match'):match.kind==='already_queued'?'Already queued':(hi?'Possible match · aap decide karo':'Possible match · you decide');
    row.append(node('span',label),node('strong',match.repo),node('small',match.reason));
    row.append(node('small',(match.downloaded?(hi?'Disk par hai':'Present on disk'):(hi?'Queue mein hai':'In queue'))+' · '+(match.size/1024**3).toFixed(2)+' GiB · '+match.revision.slice(0,12)));
    if(match.location)row.append(node('code',match.location));box.append(row);
  }
  box.append(node('p',hi?'Similar naam ka matlab identical weights nahi. Exact matches bhi download se pehle hash-check hote hain.':'Similar names do not establish identical weights. Exact existing files are still hash-checked before reuse.'));
  parent.append(box);
};
