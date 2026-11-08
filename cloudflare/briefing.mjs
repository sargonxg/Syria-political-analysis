/** Historical evidence compiler. SELECT-only; no model calls or political inference. */
const encoder=new TextEncoder();
export class BriefingInputError extends Error {}
export const FORMAT='tacitus-historical-brief/1';
const tasks={background:'Historical briefing',actors:'Recorded actor review',quality:'Evidence quality review'};
const json=x=>JSON.stringify(x);
export function parseOptions(params){
 const allowed=['country','from','to','budget','task','question'];
 for(const key of params.keys())if(!allowed.includes(key)||params.getAll(key).length!==1)throw new BriefingInputError('Invalid or duplicate parameter: '+key);
 const country=params.get('country')||'SY',from=params.get('from')||'2014',to=params.get('to')||'2016';
 if(!/^[A-Z]{2}$/.test(country))throw new BriefingInputError('Use a dataset country code.');
 if(!/^20[0-2][0-9]$/.test(from)||!/^20[0-2][0-9]$/.test(to)||+from<2000||+to>2025||+from>+to)throw new BriefingInputError('Choose a valid interval within 2000–2025.');
 const budget=params.get('budget')||'16000';
 if(!/^[0-9]+$/.test(budget)||+budget<4096||+budget>64000)throw new BriefingInputError('Context budget must be 4096–64000 UTF-8 bytes.');
 const task=params.get('task')||'background';
 if(!Object.hasOwn(tasks,task))throw new BriefingInputError('Unknown briefing task.');
 const question=(params.get('question')||'Prepare a historical evidence baseline for the selected geography and period.').trim();
 if(!question||[...question].length>300||/[\u0000-\u001f\u007f]/.test(question))throw new BriefingInputError('Question must contain 1–300 characters and no control characters.');
 return {country,from:+from,to:+to,budget:+budget,task,question};
}
export async function readState(db){
 const r=await db.prepare('SELECT key,value FROM research_meta').all();
 const state=Object.fromEntries(r.results.map(x=>[x.key,JSON.parse(x.value)]));
 if(state.state!=='ready'||state.schema_version!==1||state.format!=='policy-research-db/1')throw new Error('Research database is not ready.');
 return state;
}
export function predicate(o){
 return {sql:'country_code=? AND date_start<=? AND date_end>=?',args:[o.country,o.to+'-12-31',o.from+'-01-01']};
}
export async function compileBrief(db,o){
 const state=await readState(db);
 const country=state.countries.find(c=>c.code===o.country);
 if(!country)throw new BriefingInputError('Country is not in this dataset.');
 const p=predicate(o);
 const partition=o.task==='actors'?'side_a,side_b':o.task==='quality'?'geography_precision,date_precision':"substr(date_start,1,7),violence_type";
 const queries=[
  db.prepare('SELECT count(*) AS records FROM events WHERE '+p.sql).bind(...p.args),
  db.prepare('SELECT event_year AS year,count(*) AS records FROM events WHERE '+p.sql+' GROUP BY event_year ORDER BY event_year').bind(...p.args),
  db.prepare('SELECT geography_precision AS code,count(*) AS records FROM events WHERE '+p.sql+' GROUP BY geography_precision ORDER BY geography_precision').bind(...p.args),
  db.prepare('SELECT date_precision AS code,count(*) AS records FROM events WHERE '+p.sql+' GROUP BY date_precision ORDER BY date_precision').bind(...p.args),
  db.prepare('SELECT record_json FROM (SELECT id,date_start,record_json,ROW_NUMBER() OVER (PARTITION BY '+partition+' ORDER BY date_start DESC,id DESC) AS rank FROM events WHERE '+p.sql+') AS ranked ORDER BY rank,date_start DESC,id DESC LIMIT 128').bind(...p.args),
  db.prepare('SELECT metadata_json FROM datasets WHERE id=?').bind('ucdp-ged-26.1')
 ];
 const results=await db.batch(queries),matched=results[0].results[0].records;
 const candidates=results[4].results.map(x=>JSON.parse(x.record_json));
 const packet={format:FORMAT,task:tasks[o.task],question:o.question,scope:{country_code:o.country,country_name:country.name,from:o.from+'-01-01',to:o.to+'-12-31',date_match:'provider interval overlaps requested interval'},snapshot_id:state.snapshot.id,source_manifest_sha256:state.snapshot.manifests['ucdp-ged-snapshot'],dataset:JSON.parse(results[5].results[0].metadata_json),overview:{matched_records:matched,timeline:results[1].results,geography_precision:results[2].results,date_precision:results[3].results},selection:{method:'Round-robin representatives by '+partition+'; date descending within each stratum; deterministic greedy byte packing.',candidate_limit:128,candidates_considered:candidates.length,selected_records:0,omitted_matching_records:matched},evidence:[],analyst_assessment:null,review_status:'not_reviewed',limitations:['Historical UCDP provider records, not a live feed or independently corroborated intelligence.','Provider country categories and original date/location precision are retained. They are not an independent boundary determination.','Recorded sides do not establish negotiating representation, consent, alliance, current control, or causation.','Question is an analyst-supplied task label; selection is structured and deterministic, not semantic retrieval.','This briefing format is separate from native TACITUS capsules. No model generation or quality/cost/token savings are claimed.']};
 if(encoder.encode(json(packet)).length>o.budget)throw new Error('Context budget is too small for the required provenance and qualifications.');
 for(const record of candidates){
  packet.evidence.push(record);packet.selection.selected_records=packet.evidence.length;packet.selection.omitted_matching_records=matched-packet.evidence.length;
  if(encoder.encode(json(packet)).length>o.budget){packet.evidence.pop();packet.selection.selected_records=packet.evidence.length;packet.selection.omitted_matching_records=matched-packet.evidence.length;}
 }
 if(matched&&packet.evidence.length===0)throw new Error('No complete provider record fits this context budget. Increase the byte budget.');
 for(const record of packet.evidence){
  if(!record.attributes||Object.keys(record.attributes).length!==49)throw new Error('Original provider fields are incomplete.');
  const canonical=JSON.stringify(Object.fromEntries(Object.keys(record.attributes).sort().map(k=>[k,record.attributes[k]])));
  const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',encoder.encode(canonical))),v=>v.toString(16).padStart(2,'0')).join('');
  if(digest!==record.raw_record_sha256)throw new Error('Original provider fields failed their recorded checksum.');
 }
 const payload=json(packet),bytes=encoder.encode(payload);
 const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');
 const receipt={format:'tacitus-brief-receipt/1',payload_sha256:hash,payload_bytes:bytes.length,budget_bytes:o.budget,matched_records:matched,selected_records:packet.evidence.length,omitted_matching_records:matched-packet.evidence.length,candidates_considered:candidates.length,unconsidered_matching_records:Math.max(0,matched-candidates.length),considered_but_not_packed:candidates.length-packet.evidence.length,budget_scope:'Exact compact JSON packet only. Markdown and this receipt add overhead.',model_calls:0};
 return {packet,payload,receipt,markdown:renderBrief(packet,receipt)};
}
function md(value){return String(value??'').replaceAll('|','\\|').replace(/[\r\n]+/g,' ');}
export function renderBrief(p,r){
 const lines=['# '+p.task+' · '+p.scope.country_name,'',p.question,'','## Scope',p.scope.from+' to '+p.scope.to+'; provider intervals overlap this window.','',p.overview.matched_records.toLocaleString('en-US')+' matching provider records. '+r.selected_records+' complete records selected; '+r.omitted_matching_records+' omitted. This is a bounded evidence worksheet, not a completed assessment.','','## Annual observations','| Provider year | Records |','| --- | ---: |',...p.overview.timeline.map(x=>'| '+x.year+' | '+x.records+' |'),'','## Selected evidence'];
 for(const e of p.evidence){const a=e.attributes;lines.push('','### '+e.id,'- Provider interval: '+e.date_start+' to '+e.date_end,'- Recorded sides: '+md(a.side_a)+' / '+md(a.side_b),'- Location: '+md(a.where_coordinates||a.adm_1)+'; provider geography precision '+a.where_prec+'; date precision '+a.date_prec,'- Provider source citation: '+md(a.source_article),'- Provider headline: '+md(a.source_headline),'- Canonical provider-field SHA-256: '+e.raw_record_sha256);}
 lines.push('','## Analyst review before use','- Which source reports independently corroborate these observations?','- How do the original date/location precision codes affect the question?','- Which relevant perspectives and non-violent developments are absent?','- What additional evidence would be required to discuss mediation, consent, or representation?','','## Analyst assessment','Pending. No analytical judgment has been generated or approved.','','## Provenance',p.dataset.title+' · '+p.dataset.publisher+' · '+p.dataset.license,p.dataset.url,'Snapshot: '+p.snapshot_id,'Context payload SHA-256: '+r.payload_sha256,'Context payload bytes: '+r.payload_bytes+' / '+r.budget_bytes,'',...p.limitations.map(x=>'- '+x),'');
 return lines.join('\n');
}
export async function overview(db,params){
 const o=parseOptions(params),state=await readState(db),p=predicate(o);
 if(!state.countries.some(c=>c.code===o.country))throw new BriefingInputError('Country is not in this dataset.');
 const results=await db.batch([
  db.prepare('SELECT count(*) AS records FROM events WHERE '+p.sql).bind(...p.args),
  db.prepare('SELECT event_year AS year,count(*) AS records FROM events WHERE '+p.sql+' GROUP BY event_year ORDER BY event_year').bind(...p.args),
  db.prepare('SELECT ROUND(longitude*4)/4 AS longitude,ROUND(latitude*4)/4 AS latitude,count(*) AS records FROM events WHERE '+p.sql+' AND longitude BETWEEN -180 AND 180 AND latitude BETWEEN -90 AND 90 GROUP BY ROUND(longitude*4),ROUND(latitude*4) ORDER BY records DESC,longitude,latitude LIMIT 2049').bind(...p.args),
  db.prepare('SELECT side_a,side_b,count(*) AS records FROM events WHERE '+p.sql+' GROUP BY side_a,side_b ORDER BY records DESC,side_a,side_b LIMIT 16').bind(...p.args),
  db.prepare('SELECT count(*) AS records FROM events WHERE '+p.sql+' AND longitude BETWEEN -180 AND 180 AND latitude BETWEEN -90 AND 90').bind(...p.args)
 ]);
 const cells=results[2].results.slice(0,2048);
 return {format:'tacitus-evidence-overview/1',backend:'database',snapshot_id:state.snapshot.id,scope:o,matched:results[0].results[0].records,timeline:results[1].results,cells,pairs:results[3].results,geography:{cell_degrees:0.25,cell_limit:2048,cells_truncated:results[2].results.length>2048,geocoded_records:results[4].results[0].records,plotted_records:cells.reduce((n,c)=>n+c.records,0),interpretation:'Quarter-degree bins of provider coordinates. Bin centers are navigation marks, not exact event locations or control areas.'}};
}

