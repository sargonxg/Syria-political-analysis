/** Portable, source-span semantic context. Curated annotations and lexical proposals remain unreviewed. */
const enc=new TextEncoder();
export const semanticFormat='tacitus-semantic-document/1';
export const hashText=async text=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',enc.encode(text))),n=>n.toString(16).padStart(2,'0')).join('');
const size=x=>enc.encode(JSON.stringify(x)).length;
const required=(condition,message)=>{if(!condition)throw Error(message);};
export async function validateDocument(model){
 required(model?.format===semanticFormat,'Unsupported semantic document format.');
 const d=model.document;required(d&&typeof d.text==='string'&&enc.encode(d.text).length<=32768,'Source text must be at most 32 KiB UTF-8.');
 required(typeof d.id==='string'&&typeof d.title==='string'&&d.title.trim().length>0&&d.title.length<=200,'Document identity and title are required.');
 required(d.published_on===null||/^\d{4}-\d{2}-\d{2}$/.test(d.published_on),'Source publication date must be known ISO date or null.');
 required(!d.text.includes('\u0000')&&d.offset_unit==='UTF-16 code units','Source offsets must use UTF-16 code units.');
 required(await hashText(d.text)===d.text_sha256,'Source text checksum mismatch.');
 required(size(model)<=524288,'Document model exceeds 512 KiB.');
 if(d.url)required(['https:','http:'].includes(new URL(d.url).protocol),'Source URL must use HTTP or HTTPS.');
 const spans=new Map(),assertions=new Set(),entities=new Map((model.entities||[]).map(e=>[e.id,e]));
 required(entities.size===model.entities.length,'Duplicate entity.');
 const classes=new Set(model.ontology.classes.map(c=>c.id)),relations=new Map(model.ontology.relations.map(r=>[r.id,r])),concepts=new Set(model.ontology.concepts.map(c=>c.id));
 required(Array.isArray(model.spans)&&model.spans.length<=256&&Array.isArray(model.assertions)&&model.assertions.length<=256,'Too many source spans or assertions.');
 for(const s of model.spans){required(typeof s.id==='string'&&!spans.has(s.id),'Duplicate source span.');required(Number.isInteger(s.start)&&Number.isInteger(s.end)&&s.start>=0&&s.end>s.start&&s.end<=d.text.length&&d.text.slice(s.start,s.end)===s.quote,'Source span does not match its exact text.');spans.set(s.id,s);}
 for(const e of entities.values())required(classes.has(e.type),'Unknown entity type.');
 for(const a of model.assertions){
  required(typeof a.id==='string'&&!assertions.has(a.id),'Duplicate assertion.');assertions.add(a.id);
  required(a.human_review_recorded===false&&['needs_source_check','not_reviewed'].includes(a.review_state),'This workflow does not assert completed human review.');
  const relation=relations.get(a.predicate),subject=entities.get(a.subject_id),object=entities.get(a.object_id);
  required(relation&&subject&&object,'Unknown relation or entity.');
  required(relation.domain.includes(subject.type)&&relation.range.includes(object.type),'Ontology domain/range mismatch.');
  required(a.evidence_span_ids?.length&&a.evidence_span_ids.every(id=>spans.has(id))&&(a.required_context_span_ids||[]).every(id=>spans.has(id)),'Assertion has missing source evidence or required context.');
  required(a.concept_ids.every(id=>concepts.has(id)),'Assertion references an unknown concept.');
  required(a.temporal_scope&&a.temporal_scope.current_applicability_assessed===false&&a.temporal_scope.implementation_period_verified===false,'Do not promote document language into verified implementation.');
 }
 required(Object.keys(model.tasks||{}).length<=16,'Too many task profiles.');
 for(const t of Object.values(model.tasks||{}))required(t.assertion_ids.every(id=>assertions.has(id)),'Task references an unknown assertion.');
 return model;
}
function makePacket(model,task){
 const d=model.document;
 return {format:'tacitus-semantic-context/1',task:{id:task,label:model.tasks[task].label,selection_basis:'Explicit task profile over unreviewed assertion proposals; not model-ranked retrieval.'},document:{id:d.id,title:d.title,issuer:d.issuer,published_on:d.published_on,url:d.url,text_sha256:d.text_sha256,primary_pdf_sha256:d.primary_pdf_sha256||null,source_note:d.source_note,rights_note:d.rights_note,offset_unit:d.offset_unit},ontology:{namespace:model.ontology.namespace,version:model.ontology.version,status:model.ontology.status,classes:[],relations:[],concepts:[]},entities:[],spans:[],assertions:[],omissions:[],review_status:'not_reviewed',analyst_assessment:null,limitations:['Source-linked proposals, not verified political facts or a current implementation assessment.','A source checksum establishes consistency with this text, not independent corroboration.','Whole evidence passages and declared context dependencies are retained; quotes are not shortened to fit.','Context-byte measurements do not establish model quality, token savings or inference cost.']};
}
function populate(packet,model,selected){
 const chosen=model.assertions.filter(a=>selected.includes(a.id));
 const spanIds=new Set(chosen.flatMap(a=>[...a.evidence_span_ids,...(a.required_context_span_ids||[])]));
 const entityIds=new Set(chosen.flatMap(a=>[a.subject_id,a.object_id]));
 const relations=new Set(chosen.map(a=>a.predicate)),concepts=new Set(chosen.flatMap(a=>a.concept_ids));
 packet.assertions=chosen;packet.spans=model.spans.filter(s=>spanIds.has(s.id));
 packet.entities=model.entities.filter(e=>entityIds.has(e.id)).map(e=>({id:e.id,type:e.type,label:e.label}));
 const classes=new Set(packet.entities.map(e=>e.type));
 packet.ontology.classes=model.ontology.classes.filter(c=>classes.has(c.id)).map(c=>({id:c.id,label:c.label,definition:c.definition,scope_note:c.scope_note}));
 packet.ontology.relations=model.ontology.relations.filter(r=>relations.has(r.id)).map(r=>({id:r.id,label:r.label,definition:r.definition,domain:r.domain,range:r.range}));
 packet.ontology.concepts=model.ontology.concepts.filter(c=>concepts.has(c.id)).map(c=>({id:c.id,label:c.pref_label?.en||c.label,scope_note:c.scope_note}));
 packet.omissions=model.assertions.filter(a=>!selected.includes(a.id)).map(a=>({id:a.id,reason:model.tasks[packet.task.id].assertion_ids.includes(a.id)?'Does not fit the exact byte budget.':'Outside the selected task profile.'}));
}
export async function compileDocumentContext(model,{task='mediation',budget=12000}={}){
 await validateDocument(model);required(Object.hasOwn(model.tasks,task),'Unknown task profile.');
 required(Number.isInteger(budget)&&budget>=2048&&budget<=64000,'Context budget must be 2048–64000 bytes.');
 const packet=makePacket(model,task),selected=[];populate(packet,model,selected);
 required(size(packet)<=budget,'Context budget cannot retain required provenance.');
 for(const id of model.tasks[task].assertion_ids){selected.push(id);populate(packet,model,selected);if(size(packet)>budget){selected.pop();populate(packet,model,selected);}}
 required(!model.tasks[task].assertion_ids.length||selected.length,'Context budget cannot retain one assertion with its complete evidence and qualifications.');
 const payload=JSON.stringify(packet),receipt={format:'tacitus-semantic-receipt/1',payload_bytes:enc.encode(payload).length,budget_bytes:budget,payload_sha256:await hashText(payload),source_text_sha256:model.document.text_sha256,selected_assertions:packet.assertions.length,unique_evidence_spans:packet.spans.length,omitted_assertions:packet.omissions.length,model_calls:0,review_status:'not_reviewed'};
 return {packet,payload,receipt,graph:toJSONLD(packet),markdown:toWorksheet(packet,receipt)};
}
export function toJSONLD(packet){
 const ns='urn:tacitus:semantic:',documentId=ns+'document:'+packet.document.id;
 const graph=[{'@id':documentId,'@type':'policy:Document','dcterms:title':packet.document.title,'dcterms:issued':packet.document.published_on,'dcterms:creator':packet.document.issuer,'dcterms:source':packet.document.url||null,'policy:sourceTextSHA256':packet.document.text_sha256}];
 for(const e of packet.entities)graph.push({'@id':ns+'entity:'+e.id,'@type':'policy:'+e.type,'rdfs:label':e.label});
 for(const s of packet.spans)graph.push({'@id':ns+'span:'+s.id,'@type':'policy:EvidenceSpan','prov:wasDerivedFrom':{'@id':documentId},'policy:quote':s.quote,'policy:startUTF16':s.start,'policy:endUTF16':s.end,'policy:locator':s.locator});
 for(const a of packet.assertions)graph.push({'@id':ns+'assertion:'+a.id,'@type':'rdf:Statement','rdf:subject':{'@id':ns+'entity:'+a.subject_id},'rdf:predicate':{'@id':'policy:'+a.predicate},'rdf:object':{'@id':ns+'entity:'+a.object_id},'prov:wasDerivedFrom':a.evidence_span_ids.map(id=>({'@id':ns+'span:'+id})),'policy:requiredContext':(a.required_context_span_ids||[]).map(id=>({'@id':ns+'span:'+id})),'policy:sourceVerb':a.source_verb,'policy:reviewState':a.review_state,'policy:qualifications':a.qualifications,'policy:temporalScope':a.temporal_scope,'dcterms:subject':a.concept_ids.map(id=>({'@id':ns+'concept:'+id}))});
 for(const c of packet.ontology.classes)graph.push({'@id':'policy:'+c.id,'@type':'rdfs:Class','rdfs:label':c.label,'rdfs:comment':c.definition});
 for(const r of packet.ontology.relations)graph.push({'@id':'policy:'+r.id,'@type':'rdf:Property','rdfs:label':r.label||r.id,'rdfs:comment':r.definition,'policy:allowedDomainType':r.domain.map(id=>({'@id':'policy:'+id})),'policy:allowedRangeType':r.range.map(id=>({'@id':'policy:'+id}))});
 for(const c of packet.ontology.concepts)graph.push({'@id':ns+'concept:'+c.id,'@type':'skos:Concept','skos:prefLabel':c.label,'skos:scopeNote':c.scope_note});
 return {'@context':{policy:packet.ontology.namespace,rdf:'http://www.w3.org/1999/02/22-rdf-syntax-ns#',rdfs:'http://www.w3.org/2000/01/rdf-schema#',prov:'http://www.w3.org/ns/prov#',skos:'http://www.w3.org/2004/02/skos/core#',dcterms:'http://purl.org/dc/terms/'},'@graph':graph};
}
function toWorksheet(p,r){
 return ['# '+p.task.label,'',p.document.title,p.document.url||'Local user-supplied text','Source date: '+(p.document.published_on||'Unknown'),'',...p.assertions.flatMap(a=>['## '+a.label,'',a.statement,'','Source verb: '+a.source_verb,'Review: '+a.review_state,...a.qualifications.map(q=>'- '+q),'',...a.evidence_span_ids.map(id=>{const s=p.spans.find(s=>s.id===id);return s.locator+':\n\n> '+s.quote;}),...(a.required_context_span_ids||[]).map(id=>{const s=p.spans.find(s=>s.id===id);return 'Required context: '+s.locator+'\n\n> '+s.quote;}),'']),'## Analyst review','Pending. Check source wording, conditions, authority, scope, implementation evidence and missing perspectives.','','## Receipt','Source text SHA-256: '+r.source_text_sha256,'Context SHA-256: '+r.payload_sha256,'Context bytes: '+r.payload_bytes+' / '+r.budget_bytes,'',...p.limitations.map(x=>'- '+x),''].join('\n');
}
export async function proposeDocument(text,{title='Local document'}={}){
 required(typeof text==='string'&&text.trim()&&enc.encode(text).length<=32768&&!text.includes('\u0000'),'Paste 1–32768 UTF-8 bytes of text without NUL.');
 const sourceHash=await hashText(text),documentId='local-'+sourceHash.slice(0,16),spans=[],assertions=[],entities=[{id:documentId,type:'Document',label:title.slice(0,200)}];
 const expression=/\b(requests?|calls? (?:upon|on|for)|expresses? (?:its )?support|decides?|shall|should|must|may)\b/i;
 const blocks=[...text.matchAll(/[^\r\n]+(?:\r?\n(?!\r?\n)[^\r\n]+)*/g)].slice(0,128);
 for(const block of blocks){
  const trigger=block[0].match(expression);if(!trigger)continue;
  const n=assertions.length+1,id='proposal-'+n,spanId='local-span-'+n,objectId='expression-'+n;
  spans.push({id:spanId,start:block.index,end:block.index+block[0].length,quote:block[0],locator:'Local paragraph '+(blocks.indexOf(block)+1)});
  entities.push({id:objectId,type:'TextualProposal',label:block[0].slice(0,110)});
  assertions.push({id,label:'Expression candidate '+n,statement:block[0],subject_id:documentId,predicate:'contains_expression',object_id:objectId,source_verb:trigger[0],evidence_span_ids:[spanId],required_context_span_ids:[],concept_ids:[],temporal_scope:{source_statement_on:null,current_applicability_assessed:false,implementation_period_verified:false},qualifications:['Lexical candidate only. Issuer, addressee, legal effect, negation, conditions and implementation require human review.'],review_state:'not_reviewed',human_review_recorded:false});
 }
 const model={format:semanticFormat,document:{id:documentId,title:title.slice(0,200),issuer:null,published_on:null,url:null,text,text_sha256:sourceHash,source_note:'User-supplied local text. Paragraph-level lexical proposals; no semantic model or entity resolution ran.',offset_unit:'UTF-16 code units',rights_note:'User-supplied source; no rights transfer is inferred.'},spans,assertions,entities,ontology:{namespace:'urn:tacitus:local-text:',version:'1.0.0',status:'Lexical candidate vocabulary; not an approved political ontology.',classes:[{id:'Document',label:'Document',definition:'User-supplied text with unknown authority.'},{id:'TextualProposal',label:'Textual proposal',definition:'A paragraph containing a literal expression trigger; not an accepted assertion.'}],relations:[{id:'contains_expression',label:'contains expression',definition:'Literal source language only.',domain:['Document'],range:['TextualProposal']}],concepts:[]},tasks:{all:{label:'Local expression review',assertion_ids:assertions.map(a=>a.id)}}};
 return validateDocument(model);
}

