/* Original synthetic teaching fixtures. No external source or inference calls. */
(function (root) {
  'use strict';
  const sources = Object.freeze([
    Object.freeze({id:'dispatch-01',title:'Harbor council dispatch',date:'2030-04-02',text:'The council said the harbor would reopen on 5 April if the inspection was completed. The inspection had not yet been completed.',rights:'Original synthetic TACITUS teaching fixture.'}),
    Object.freeze({id:'dispatch-02',title:'Inspector’s field note',date:'2030-04-06',text:'The inspector reported completing the inspection on 6 April. This note does not confirm when the harbor reopened.',rights:'Original synthetic TACITUS teaching fixture.'})
  ]);
  const evidenceQuote='The council said the harbor would reopen on 5 April if the inspection was completed.';
  function validateQuote(source,quote){return typeof quote==='string' && quote.length>0 && source.text.includes(quote);}
  function eligible(state){return state.condition===true && state.attribution===true && state.time===true;}
  function receipt(state,project,notes=''){
    if(!eligible(state)||state.review!==true) throw new Error('Complete all rooms and acknowledge the review boundary before export.');
    const source=sources[0],start=source.text.indexOf(evidenceQuote);
    return {schema:'tacitus-teaching-brief/1',synthetic:true,project,task:'Did the harbor reopen?',review_status:'learner-checked-synthetic-exercise',sources:sources.map(s=>({...s})),evidence:[{source_id:source.id,quote:evidenceQuote,start,end:start+evidenceQuote.length,offset_unit:'UTF-16 code units'}],as_of:'2030-04-06',finding:'The council announced a conditional reopening date. The inspector later reported completing the inspection. Actual reopening is not confirmed by these two dispatches.',omissions:['No operational harbor record.','No independent confirmation of the inspection.','No evidence after 6 April 2030.'],analyst_notes:notes,limitations:['Synthetic teaching export; not an application capsule or import contract.','Exact quotation matching does not establish truth or semantic entailment.','Learner acknowledgement is not authenticated expert approval.']};
  }
  const api={sources,evidenceQuote,validateQuote,eligible,receipt};
  if(typeof module==='object'&&module.exports)module.exports=api;else root.MansionEngine=api;
})(globalThis);
