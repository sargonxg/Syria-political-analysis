import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
import {sqliteBinding} from './local-api.mjs';
import {compileBrief,parseOptions,overview} from './briefing.mjs';
const root=fileURLToPath(new URL('../',import.meta.url));
const snapshot=resolve(root,'data/historical/ucdp-ged-26.1');
const manifest=JSON.parse(readFileSync(resolve(snapshot,'manifest.json'),'utf8'));
const rows=[];
for(const shard of manifest.raw_shards.filter(x=>x.country_code==='SY')){rows.push(...JSON.parse(readFileSync(resolve(snapshot,shard.path.replace('./data/events-raw/','events-raw/')),'utf8')).records);if(rows.length>=8)break;}
const fixture=rows.slice(0,8);
function database(){
 const db=new DatabaseSync(':memory:');db.exec(readFileSync(resolve(root,'cloudflare/schema.sql'),'utf8'));
 const metadata=manifest.datasets[0];
 db.prepare('INSERT INTO datasets VALUES (?,?,?,?,?,?,?,?)').run(metadata.id,metadata.title,metadata.version,metadata.publisher,metadata.url,metadata.license,metadata.sha256,JSON.stringify(metadata));
 for(const r of fixture){const a=r.attributes;db.prepare('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)').run(r.id,r.dataset_id,r.country_code,+a.year,r.date_start,r.date_end,+a.type_of_violence,+a.where_prec,+a.date_prec,a.side_a,a.side_b,(a.side_a+' '+a.side_b).toLowerCase(),r.latitude,r.longitude,+a.low,+a.best,+a.high,r.raw_record_sha256,JSON.stringify(r));}
 const meta={format:'policy-research-db/1',schema_version:1,state:'ready',countries:[{code:'SY',name:'Syria',events:fixture.length}],snapshot:{id:'a'.repeat(64),manifests:{'ucdp-ged-snapshot':'b'.repeat(64)}}};
 for(const[k,v]of Object.entries(meta))db.prepare('INSERT INTO research_meta VALUES (?,?)').run(k,JSON.stringify(v));
 return db;
}
const opts=(extra={})=>parseOptions(new URLSearchParams({country:'SY',from:'2000',to:'2025',budget:'16000',...extra}));
test('strict parameters reject unknowns, duplicates, reversed windows and invalid budgets',()=>{
 for(const p of ['country=SY&country=IQ','country=SY&sql=DROP','from=2025&to=2000','budget=1','from=1999','to=2026','task=prediction','question=%00'])assert.throws(()=>parseOptions(new URLSearchParams(p)));
});
test('all three tasks produce deterministic bounded complete-source packets',async()=>{
 const db=database();try{for(const task of ['background','actors','quality']){
 const a=await compileBrief(sqliteBinding(db),opts({task})),b=await compileBrief(sqliteBinding(db),opts({task}));
 assert.equal(a.payload,b.payload);assert.ok(a.receipt.payload_bytes<=16000);assert.equal(Buffer.byteLength(a.payload),a.receipt.payload_bytes);
 assert.ok(a.packet.evidence.length);assert.equal(a.receipt.matched_records,fixture.length);assert.equal(a.receipt.omitted_matching_records,fixture.length-a.packet.evidence.length);
 for(const r of a.packet.evidence){assert.equal(Object.keys(r.attributes).length,49);assert.deepEqual(r,fixture.find(f=>f.id===r.id));}
 assert.equal(a.packet.analyst_assessment,null);assert.equal(a.receipt.model_calls,0);assert.match(a.markdown,/Pending/);
 }}finally{db.close();}
});
test('unanswerable date scope returns an explicit empty evidence worksheet',async()=>{
 const db=database();try{const out=await compileBrief(sqliteBinding(db),opts({from:'2025',to:'2025'}));assert.equal(out.receipt.matched_records,0);assert.equal(out.packet.evidence.length,0);assert.equal(out.packet.analyst_assessment,null);}finally{db.close();}
});
test('a SQL-like question is retained as text and cannot alter the database',async()=>{
 const db=database();try{const q="'; DROP TABLE events; --";const out=await compileBrief(sqliteBinding(db),opts({question:q}));assert.equal(out.packet.question,q);assert.equal(db.prepare('SELECT count(*) AS n FROM events').get().n,fixture.length);}finally{db.close();}
});
test('tampered source fields refuse export',async()=>{
 const db=database();try{for(const r of fixture){const changed=structuredClone(r);changed.attributes.source_article='tampered';db.prepare('UPDATE events SET record_json=? WHERE id=?').run(JSON.stringify(changed),r.id);}await assert.rejects(()=>compileBrief(sqliteBinding(db),opts()),/checksum/);}finally{db.close();}
});
test('incomplete database refuses compilation and unknown country refuses',async()=>{
 const db=database();try{await assert.rejects(()=>compileBrief(sqliteBinding(db),opts({country:'ZZ'})),/not in this dataset/);db.prepare('DELETE FROM research_meta WHERE key=?').run('state');await assert.rejects(()=>compileBrief(sqliteBinding(db),opts()),/not ready/);}finally{db.close();}
});
test('map bins account for plotted records and preserve real count totals',async()=>{
 const db=database();try{const out=await overview(sqliteBinding(db),new URLSearchParams({country:'SY',from:'2000',to:'2025'}));assert.equal(out.matched,fixture.length);assert.equal(out.geography.plotted_records,out.cells.reduce((n,c)=>n+c.records,0));assert.equal(out.timeline.reduce((n,y)=>n+y.records,0),fixture.length);assert.ok(out.cells.length<=2048);}finally{db.close();}
});

