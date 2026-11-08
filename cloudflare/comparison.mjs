/** Source-linked period comparison; SELECT-only and deterministic. No model calls. */
import {readState,BriefingInputError} from './briefing.mjs';
const enc=new TextEncoder(),bytes=x=>enc.encode(JSON.stringify(x)).length;
const compactFields=['side_a','side_b','type_of_violence','where_coordinates','adm_1','where_prec','date_prec','source_article','source_headline','source_date'];
const digest=async text=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',enc.encode(text))),x=>x.toString(16).padStart(2,'0')).join('');
export function parseComparison(params){
 const allowed=['country','from','to','baseline_from','baseline_to','budget','mode','question'];
 for(const key of params.keys())if(!allowed.includes(key)||params.getAll(key).length!==1||params.get(key)==='')throw new BriefingInputError('Invalid or duplicate comparison parameter: '+key);
 const o={country:params.get('country')||'SY',from:Number(params.get('from')||2014),to:Number(params.get('to')||2016),baseline_from:Number(params.get('baseline_from')||2011),baseline_to:Number(params.get('baseline_to')||2013),budget:Number(params.get('budget')||16000),mode:params.get('mode')||'compact',question:(params.get('question')||'What changed in the recorded historical evidence between these periods?').trim()};
 if(!/^[A-Z]{2}$/.test(o.country))throw new BriefingInputError('Use a dataset country code.');
 for(const key of ['from','to','baseline_from','baseline_to'])if(!Number.isInteger(o[key])||o[key]<2000||o[key]>2025||params.has(key)&&!/^20[0-2][0-9]$/.test(params.get(key)))throw new BriefingInputError('Use full calendar years within 2000–2025.');
 if(o.from>o.to||o.baseline_from>o.baseline_to||o.baseline_to>=o.from)throw new BriefingInputError('Baseline must end before the focus period starts.');
 if(!Number.isInteger(o.budget)||o.budget<8000||o.budget>64000||params.has('budget')&&!/^[0-9]+$/.test(params.get('budget')))throw new BriefingInputError('Comparison budget must be 8000–64000 bytes.');
 if(!['compact','full'].includes(o.mode))throw new BriefingInputError('Mode must be compact or full.');
 if(!o.question||[...o.question].length>300||/[\u0000-\u001f\u007f]/.test(o.question))throw new BriefingInputError('Question must contain 1–300 characters without controls.');
 return o;
}
function interval(from,to){return {from:from+'-01-01',to:to+'-12-31',years:to-from+1};}
function condition(o,p){return {sql:'country_code=? AND date_start<=? AND date_end>=?',args:[o.country,p.to,p.from]};}
async function period(db,o,p,withCandidates){
 const where=condition(o,p);
 const sql=[
 'SELECT count(*) AS records FROM events WHERE '+where.sql,
 'SELECT event_year AS year,count(*) AS records FROM events WHERE '+where.sql+' GROUP BY event_year ORDER BY event_year',
 'SELECT geography_precision AS code,count(*) AS records FROM events WHERE '+where.sql+' GROUP BY geography_precision ORDER BY geography_precision'
 ];
 if(withCandidates)sql.push('SELECT record_json FROM (SELECT id,date_start,record_json,ROW_NUMBER() OVER (PARTITION BY substr(date_start,1,7),violence_type ORDER BY date_start DESC,id DESC) AS ranking FROM events WHERE '+where.sql+') ORDER BY ranking,date_start DESC,id DESC LIMIT 64');
 const r=await db.batch(sql.map(q=>db.prepare(q).bind(...where.args)));
 return {from:p.from,to:p.to,calendar_years:p.years,matched_records:r[0].results[0].records,records_per_calendar_year:r[0].results[0].records/p.years,timeline:r[1].results,geography_precision:r[2].results,...(withCandidates?{candidates:r[3].results.map(x=>JSON.parse(x.record_json))}:{})};
}
export async function comparePeriods(db,o,withCandidates=false){
 const state=await readState(db),country=state.countries.find(c=>c.code===o.country);
 if(!country)throw new BriefingInputError('Country is not in this dataset.');
 const base=interval(o.baseline_from,o.baseline_to),focus=interval(o.from,o.to);
 const [baseline,current]=await Promise.all([period(db,o,base,withCandidates),period(db,o,focus,withCandidates)]);
 const shared=await db.prepare('SELECT count(*) AS records FROM events WHERE country_code=? AND date_start<=? AND date_end>=? AND date_start<=? AND date_end>=?').bind(o.country,base.to,base.from,focus.to,focus.from).first();
 const annualDelta=current.records_per_calendar_year-baseline.records_per_calendar_year;
 const pairs=await db.prepare('SELECT side_a,side_b,sum(CASE WHEN date_start<=? AND date_end>=? THEN 1 ELSE 0 END) AS baseline_records,sum(CASE WHEN date_start<=? AND date_end>=? THEN 1 ELSE 0 END) AS focus_records FROM events WHERE country_code=? AND ((date_start<=? AND date_end>=?) OR (date_start<=? AND date_end>=?)) GROUP BY side_a,side_b ORDER BY (baseline_records+focus_records) DESC,side_a,side_b LIMIT 13').bind(base.to,base.from,focus.to,focus.from,o.country,base.to,base.from,focus.to,focus.from).all();
 const dataset=await db.prepare('SELECT metadata_json FROM datasets WHERE id=?').bind('ucdp-ged-26.1').first();
 return {format:'tacitus-period-comparison/1',snapshot_id:state.snapshot.id,source_manifest_sha256:state.snapshot.manifests['ucdp-ged-snapshot'],dataset:JSON.parse(dataset.metadata_json),country:{code:country.code,name:country.name},baseline,focus:current,pair_comparison:pairs.results.slice(0,12),pairs_truncated:pairs.results.length>12,change:{annual_record_delta:annualDelta,annual_percent_change:baseline.records_per_calendar_year===0?null:annualDelta/baseline.records_per_calendar_year*100,shared_interval_records:shared.records},limits:{date_match:'Original provider interval overlaps each requested window; a long interval can belong to both.',pair_scope:'Up to 12 most frequent pairs by combined period record counts; each displayed count is exact within its period. Unlisted pairs remain outside this view.',interpretation:'Observation counts describe this retained provider dataset, not conflict intensity, causation, current control, negotiating consent or completeness of reporting.'}};
}
async function project(record,periods,mode){
 if(record.date_start!==String(record.attributes.date_start).slice(0,10)||record.date_end!==String(record.attributes.date_end).slice(0,10)||record.id!=='ucdp-ged:26.1:'+record.attributes.id)throw Error('Provider record envelope does not match its original fields.');
 const canonical=JSON.stringify(Object.fromEntries(Object.keys(record.attributes).sort().map(k=>[k,record.attributes[k]])));
 if(Object.keys(record.attributes).length!==49||await digest(canonical)!==record.raw_record_sha256)throw Error('Original provider fields failed checksum verification.');
 const base={id:record.id,periods,date_start:record.date_start,date_end:record.date_end,original_record_url:'/api/research/events/'+encodeURIComponent(record.id),original_fields_sha256:record.raw_record_sha256};
 return mode==='full'?{...base,record}:{...base,fields:Object.fromEntries(compactFields.map(k=>[k,record.attributes[k]??null]))};
}
export async function compileComparison(db,o){
 const overview=await comparePeriods(db,o,true),baseline=overview.baseline.candidates,focus=overview.focus.candidates;
 delete overview.baseline.candidates;delete overview.focus.candidates;
 const packet={format:'tacitus-change-context/1',question:o.question,comparison:overview,selection:{method:'Interleaved baseline/focus representatives by provider month and violence type. Deterministic whole-record projection packing.',mode:o.mode,candidate_limit_per_period:64,candidates_considered:0,selected_records:0,selected_by_period:{baseline:0,focus:0},omitted_scope_memberships:overview.baseline.matched_records+overview.focus.matched_records,retained_fields:o.mode==='compact'?compactFields:'All 49 original provider attributes; original record envelope retained.'},evidence:[],analyst_assessment:null,review_status:'not_reviewed',limitations:['Comparison is descriptive; counts are not a measure of relative conflict intensity or political success.','Compact evidence is an explicit projection, not the original full record. Original records are linked by ID and SHA-256.','Projection fidelity checks establish consistency with this snapshot, not independent corroboration.','Question is retained as a task label, not semantic retrieval. No model answer or review approval is generated.']};
 const unique=new Map();
 for(let i=0;i<Math.max(baseline.length,focus.length);i++)for(const [name,list]of [['baseline',baseline],['focus',focus]]){const r=list[i];if(!r)continue;if(unique.has(r.id))unique.get(r.id).periods.add(name);else unique.set(r.id,{record:r,periods:new Set([name])});}
 // Membership follows source intervals, including records which overlap both windows.
 for(const item of unique.values())for(const [name,p]of [['baseline',overview.baseline],['focus',overview.focus]])if(item.record.date_start<=p.to&&item.record.date_end>=p.from)item.periods.add(name);
 packet.selection.candidates_considered=unique.size;
 const update=()=>{packet.selection.selected_records=packet.evidence.length;packet.selection.selected_by_period={baseline:packet.evidence.filter(e=>e.periods.includes('baseline')).length,focus:packet.evidence.filter(e=>e.periods.includes('focus')).length};packet.selection.omitted_scope_memberships=overview.baseline.matched_records+overview.focus.matched_records-packet.selection.selected_by_period.baseline-packet.selection.selected_by_period.focus;};
 if(bytes(packet)>o.budget)throw Error('Comparison budget cannot retain its required provenance. Increase the budget.');
 for(const item of unique.values()){
  const selected=await project(item.record,[...item.periods].sort(),o.mode);packet.evidence.push(selected);update();
  if(bytes(packet)>o.budget){packet.evidence.pop();update();}
 }
 for(const name of ['baseline','focus'])if(overview[name].matched_records&&!packet.selection.selected_by_period[name])throw Error('Comparison budget cannot retain evidence from both nonempty periods. Increase the budget.');
 const payload=JSON.stringify(packet),receipt={format:'tacitus-change-receipt/1',payload_sha256:await digest(payload),payload_bytes:enc.encode(payload).length,budget_bytes:o.budget,selected_records:packet.evidence.length,selected_by_period:packet.selection.selected_by_period,omitted_scope_memberships:packet.selection.omitted_scope_memberships,mode:o.mode,model_calls:0,budget_scope:'Exact compact JSON payload. Markdown and receipt are additional files.'};
 return {packet,payload,receipt,markdown:renderComparison(packet,receipt)};
}
function safe(v){return String(v??'').replaceAll('|','\\|').replace(/[\r\n]+/g,' ');}
export function renderComparison(p,r){
 const c=p.comparison,a=c.baseline,b=c.focus;
 return ['# Historical change brief · '+c.country.name,'',p.question,'','## Compared scope','| | Baseline | Focus |','| --- | ---: | ---: |','| Interval | '+a.from+' – '+a.to+' | '+b.from+' – '+b.to+' |','| Matching provider records | '+a.matched_records+' | '+b.matched_records+' |','| Records / calendar year | '+a.records_per_calendar_year.toFixed(2)+' | '+b.records_per_calendar_year.toFixed(2)+' |','',c.change.shared_interval_records+' records overlap both windows. Counts describe the retained dataset; they are not a conflict-intensity estimate.','','## Inspectable evidence',...p.evidence.flatMap(e=>{const f=e.fields||e.record.attributes;return ['','### '+e.id+' · '+e.periods.join(' + '),'- Interval: '+e.date_start+' – '+e.date_end,'- Recorded sides: '+safe(f.side_a)+' / '+safe(f.side_b),'- Provider citation: '+safe(f.source_article),'- Provider headline: '+safe(f.source_headline),'- Original record: '+e.original_record_url,'- Original-field SHA-256: '+e.original_fields_sha256];}),'','## Review before use','- Are reporting coverage and event definitions comparable across these windows?','- Which records overlap both periods, and how does date precision affect the comparison?','- Which non-violent developments and perspectives are missing?','- What additional sources would establish negotiating positions or representation?','','## Analyst assessment','Pending. No interpretation or recommendation has been generated.','','## Receipt','Context bytes: '+r.payload_bytes+' / '+r.budget_bytes,'SHA-256: '+r.payload_sha256,'Snapshot: '+c.snapshot_id,'Data: '+c.dataset.title+' · '+c.dataset.publisher+' · '+c.dataset.license,c.dataset.url,'',...p.limitations.map(s=>'- '+s),''].join('\n');
}

