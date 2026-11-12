(function(){
  'use strict';
  const E=window.MansionEngine,P=window.MansionProject;
  const $=id=>document.getElementById(id);
  let state={condition:false,attribution:false,time:false,review:false,exported:false},room='library',notes='';
  const text=(tag,value,className)=>{const el=document.createElement(tag);el.textContent=value;if(className)el.className=className;return el;};
  const feedback=message=>{$('feedback').textContent=message;};
  function button(parent,label,action,className='choice'){const b=text('button',label,className);b.type='button';b.addEventListener('click',action);parent.append(b);return b;}
  function update(){const done=[state.condition,state.attribution,state.time,state.exported],labels=['Preserve the condition','Keep attribution','Check the clock','Export the brief'];$('inventory').replaceChildren(...labels.map((v,i)=>text('li',(done[i]?'■ ':'□ ')+v)));$('progress').textContent=`${done.filter(Boolean).length} / 4 discoveries`;}
  function source(parent,s){parent.append(text('p',`${s.id} · ${s.title} · ${s.date}`,'source-meta'),text('blockquote',s.text));}
  function show(next,focus=true){room=next;feedback('');const content=$('room-content');content.replaceChildren();document.querySelectorAll('[data-room]').forEach(b=>b.setAttribute('aria-current',String(b.dataset.room===room)));
    const titles={library:['01 / PRESERVE','The library'],map:['02 / ATTRIBUTE','The map room'],clock:['03 / DATE','The clock archive'],study:['04 / REVIEW','The analyst’s study']};$('room-label').textContent=titles[room][0];$('room-title').textContent=titles[room][1];
    if(room==='library'){
      content.append(text('p','Find the promise in its original form. Which quotation preserves the condition?'));source(content,E.sources[0]);
      button(content,'“The harbor would reopen on 5 April.”',()=>feedback('That removes “if the inspection was completed”. A confident summary can erase the most important fact.'));
      button(content,'“'+E.evidenceQuote+'”',()=>{state.condition=E.validateQuote(E.sources[0],E.evidenceQuote);update();feedback('Condition preserved. You have an exact quotation with an attributed, conditional promise. Continue to the map room.');});
      button(content,'“The inspection proves the harbor is open.”',()=>feedback('Neither dispatch says this. Keep an unsupported inference separate from the source.'));
    }
    if(room==='map'){
      content.append(text('p','A graph is useful only when its edges keep the meaning of the text. Choose the defensible relation.'));source(content,E.sources[0]);
      button(content,'Council → announced a conditional reopening → Harbor',()=>{state.attribution=true;update();feedback('Attributed statement saved. This edge records what the council said; it does not certify an opening.');});
      button(content,'Inspector → guaranteed opening on 5 April → Harbor',()=>feedback('The inspector did not make that promise. Do not merge the speaker with the subject of a later report.'));
      button(content,'Harbor → definitely open → 5 April',()=>feedback('That turns a conditional promise into an observed fact. The opening remains unconfirmed.'));
    }
    if(room==='clock'){
      content.append(text('p','Read the records as of 6 April 2030. A scheduled date and an observed date are different clocks.'));E.sources.forEach(s=>source(content,s));
      button(content,'2 April: council statement → 5 April: proposed opening → 6 April: reported inspection',()=>{state.time=true;update();feedback('Timeline preserved. As of 6 April, the actual reopening is still unknown.');});
      button(content,'5 April: confirmed opening → 6 April: inspection caused the opening',()=>feedback('The records do not confirm an opening or establish a causal chain. Do not fill a gap with a plausible story.'));
    }
    if(room==='study'){
      if(!E.eligible(state)){content.append(text('p','The brief is not ready. Visit the library, map room and clock archive to preserve the evidence, attribution and dates.'));}
      else{
        content.append(text('p','Your defensible finding','source-meta'),text('blockquote','The council announced a conditional reopening date. The inspector later reported completing the inspection. Actual reopening is not confirmed by these two dispatches.'));
        content.append(text('p','Missing evidence: operational harbor record, independent inspection confirmation, and later updates.'));
        const label=text('label','Your analyst note (optional; stays separate from evidence)');const area=document.createElement('textarea');area.maxLength=2000;area.value=notes;area.addEventListener('input',()=>{notes=area.value;});label.append(area);content.append(label);
        const review=text('label','','check'),checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.checked=state.review;review.append(checkbox,text('span','I understand this is synthetic evidence and my acknowledgement does not establish truth or expert approval.'));content.append(review);
        const download=button(content,'Download inspectable brief ↓',()=>{try{const result=E.receipt(state,P.title,notes),url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)+'\n'],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='tacitus-teaching-brief.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);state.exported=true;update();feedback('Case closed—with the uncertainty intact. Your JSON includes exact quotes, dates, source text, omissions and separate analyst notes.');}catch(error){feedback(error.message);}},'primary');download.disabled=!state.review;checkbox.addEventListener('change',()=>{state.review=checkbox.checked;download.disabled=!state.review;});
      }
    }
    if(focus)$('desk').focus({preventScroll:true});update();
  }
  document.querySelectorAll('[data-room]').forEach(b=>b.addEventListener('click',()=>{show(b.dataset.room);$('desk').scrollIntoView({behavior:'instant',block:'start'});}));
  $('reset').addEventListener('click',()=>{state={condition:false,attribution:false,time:false,review:false,exported:false};notes='';show('library');feedback('A new game has begun. No progress or notes are saved to a server.');});
  $('project-title').textContent=P.title;$('project-purpose').textContent=P.purpose;$('project-boundary').textContent=P.boundary;$('project-command').textContent=P.command;$('project-guide').href=P.guide;show('library',false);
})();
