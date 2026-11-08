import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {sqliteBinding} from './local-api.mjs';
import {parseComparison,comparePeriods,compileComparison} from './comparison.mjs';
const manifest=JSON.parse(readFileSync(new URL('../data/historical/ucdp-ged-26.1/manifest.json',import.meta.url)));
const records=[2011,2014].flatMap(year=>{
 const s=manifest.raw_shards.find(s=>s.country_code==='SY'&&s.partition_year===year);
 return JSON.parse(readFileSync(new URL('../data/historical/ucdp-ged-26.1/'+s.path.replace('./data/events-raw/','events-raw/'),import.meta.url))).records.slice(0,3);
});
function fixture(){
 const db=new DatabaseSync(':memory:');db.exec(readFileSync(new URL('./schema.sql',import.meta.url),'utf8'));
 const metadata=manifest.datasets[0];
 db.prepare('INSERT INTO datasets VALUES (?,?,?,?,?,?,?,?)').run(metadata.id,metadata.title,metadata.version,metadata.publisher,metadata.url,metadata.license,metadata.sha256,JSON.stringify(metadata));
 for(const r of records){const a=r.attributes;db.prepare('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)').run(r.id,r.dataset_id,r.country_code,+a.year,r.date_start,r.date_end,+a.type_of_violence,+a.where_prec,+a.date_prec,a.side_a,a.side_b,(a.side_a+' '+a.side_b).toLowerCase(),r.latitude,r.longitude,+a.low,+a.best,+a.high,r.raw_record_sha256,JSON.stringify(r));}
 for(const[k,v]of Object.entries({format:'policy-research-db/1',schema_version:1,state:'ready',countries:[{code:'SY',name:'Syria'}],snapshot:{id:'a'.repeat(64),manifests:{'ucdp-ged-snapshot':'b'.repeat(64)}}}))db.prepare('INSERT INTO research_meta VALUES (?,?)').run(k,JSON.stringify(v));
 return db;
}
const options=(extra={})=>parseComparison(new URLSearchParams({country:'SY',baseline_from:'2011',baseline_to:'2013',from:'2014',to:'2016',...extra}));
test('strict comparison scope rejects overlap, malformed years, duplicates and nondecimal budgets',()=>{
 for(const text of ['baseline_to=2014&from=2014','baseline_from=2012&baseline_to=2011','country=SY&country=IQ','sql=SELECT','from=2014.5','budget=8e3','mode=semantic','question=%00','question=','country=','budget='])assert.throws(()=>parseComparison(new URLSearchParams(text)));
});
test('summary counts, shared intervals and annualization match independent expected records',async()=>{
 const db=fixture();try{
 const result=await comparePeriods(sqliteBinding(db),options());
 assert.equal(result.baseline.matched_records,3);assert.equal(result.focus.matched_records,3);
 assert.equal(result.baseline.records_per_calendar_year,1);assert.equal(result.change.annual_percent_change,0);
 assert.equal(result.change.shared_interval_records,0);assert.equal(result.dataset.id,'ucdp-ged-26.1');
 const empty=await comparePeriods(sqliteBinding(db),options({baseline_from:'2000',baseline_to:'2001'}));assert.equal(empty.change.annual_percent_change,null);
 }finally{db.close();}
});
test('compact and full evidence are deterministic, exact, within budget, and cover both periods',async()=>{
 const db=fixture();try{
 for(const mode of ['compact','full'])for(const budget of [16000,32000]){
 const a=await compileComparison(sqliteBinding(db),options({mode,budget})),b=await compileComparison(sqliteBinding(db),options({mode,budget}));
 assert.equal(a.payload,b.payload);assert.equal(Buffer.byteLength(a.payload),a.receipt.payload_bytes);assert.ok(a.receipt.payload_bytes<=budget);
 assert.ok(a.receipt.selected_by_period.baseline);assert.ok(a.receipt.selected_by_period.focus);
 assert.equal(a.packet.analyst_assessment,null);assert.equal(a.receipt.model_calls,0);assert.match(a.markdown,/Pending/);
 for(const e of a.packet.evidence){const source=records.find(r=>r.id===e.id);if(mode==='full')assert.deepEqual(e.record,source);else for(const[k,v]of Object.entries(e.fields))assert.deepEqual(v,source.attributes[k]??null);}
 }
 }finally{db.close();}
});
test('corrupt fields and inconsistent outer date fail instead of exporting',async()=>{
 for(const kind of ['fields','envelope']){
 const db=fixture();try{
 for(const source of records){const changed=structuredClone(source);if(kind==='fields')changed.attributes.source_article='tampered';else changed.date_start='2000-01-01';db.prepare('UPDATE events SET record_json=? WHERE id=?').run(JSON.stringify(changed),source.id);}
 await assert.rejects(()=>compileComparison(sqliteBinding(db),options()),/checksum|envelope/);
 }finally{db.close();}
 }
});
test('incomplete database and unsupported countries fail; source text never becomes SQL',async()=>{
 const db=fixture();try{
 const question="'; DROP TABLE events; --";const result=await compileComparison(sqliteBinding(db),options({question}));assert.equal(result.packet.question,question);assert.equal(db.prepare('SELECT count(*) AS n FROM events').get().n,6);
 await assert.rejects(()=>comparePeriods(sqliteBinding(db),options({country:'ZZ'})),/not in this dataset/);
 db.prepare("DELETE FROM research_meta WHERE key='state'").run();await assert.rejects(()=>compileComparison(sqliteBinding(db),options()),/not ready/);
 }finally{db.close();}
});


test('one source interval spanning both windows is retained once with both memberships',async()=>{
 const db=fixture();try{
 const record=structuredClone(records[0]);record.date_end='2016-12-31';record.attributes.date_end='2016-12-31 00:00:00.000';
 record.raw_record_sha256=createHash('sha256').update(JSON.stringify(Object.fromEntries(Object.keys(record.attributes).sort().map(k=>[k,record.attributes[k]])))).digest('hex');
 db.prepare('UPDATE events SET date_end=?,record_json=?,raw_record_sha256=? WHERE id=?').run(record.date_end,JSON.stringify(record),record.raw_record_sha256,record.id);
 const result=await compileComparison(sqliteBinding(db),options({budget:32000}));
 assert.equal(result.packet.comparison.change.shared_interval_records,1);
 const selected=result.packet.evidence.filter(e=>e.id===record.id);assert.equal(selected.length,1);assert.deepEqual(selected[0].periods,['baseline','focus']);
 }finally{db.close();}
});
