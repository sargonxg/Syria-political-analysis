#!/usr/bin/env node
import {DatabaseSync} from 'node:sqlite';
import {performance} from 'node:perf_hooks';
import {writeFile,readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {sqliteBinding} from '../cloudflare/local-api.mjs';
import {compileComparison,parseComparison} from '../cloudflare/comparison.mjs';
const [database,output]=process.argv.slice(2);if(!database||!output)throw Error('Usage: node scripts/benchmark_comparison.mjs database output.json');
const db=new DatabaseSync(database,{readOnly:true}),binding=sqliteBinding(db);
const percentile=(xs,p)=>[...xs].sort((a,b)=>a-b)[Math.ceil(xs.length*p)-1];
const cases=[['SY',2011,2013,2014,2016],['IQ',2011,2013,2014,2017],['LB',2003,2005,2006,2006],['YE',2011,2014,2015,2020],['JO',2000,2010,2011,2025],['SY',2000,2001,2002,2003]];
const results=[];
try{
 for(const[country,bf,bt,from,to]of cases)for(const budget of [8000,16000,32000]){
  const row={country,baseline:[bf,bt],focus:[from,to],budget_bytes:budget,arms:{}};
  for(const mode of ['full','compact']){
   const opts=parseComparison(new URLSearchParams({country,baseline_from:bf,baseline_to:bt,from,to,budget,mode})),times=[];let result,refusal=null;
   for(let run=0;run<4;run++){
    const start=performance.now();
    try{
     const current=await compileComparison(binding,opts);
     if(result&&current.payload!==result.payload)throw Error('Nondeterministic packet');
     result=current;if(run)times.push(performance.now()-start);
    }catch(e){if(!e.message.includes('budget'))throw e;refusal=e.message;break;}
   }
   if(refusal){row.arms[mode]={status:'refused',reason:refusal};continue;}
   if(result.receipt.payload_bytes>budget||Buffer.byteLength(result.payload)!==result.receipt.payload_bytes)throw Error('Byte budget mismatch');
   for(const e of result.packet.evidence){
    const original=JSON.parse(db.prepare('SELECT record_json FROM events WHERE id=?').get(e.id).record_json);
    if(mode==='full'){if(JSON.stringify(original)!==JSON.stringify(e.record))throw Error('Full record mismatch');}
    else for(const[k,v]of Object.entries(e.fields))if(JSON.stringify(v)!==JSON.stringify(original.attributes[k]??null))throw Error('Projection mismatch');
   }
   for(const[name,range]of [['baseline',[bf,bt]],['focus',[from,to]]]){
    const truth=db.prepare('SELECT count(*) AS n FROM events WHERE country_code=? AND date_start<=? AND date_end>=?').get(country,range[1]+'-12-31',range[0]+'-01-01').n;
    if(result.packet.comparison[name].matched_records!==truth)throw Error('Count mismatch');
   }
   row.arms[mode]={status:'ok',payload_bytes:result.receipt.payload_bytes,selected_records:result.receipt.selected_records,selected_by_period:result.receipt.selected_by_period,sha256:result.receipt.payload_sha256,p50_ms:percentile(times,.5),p95_ms:percentile(times,.95),measured_runs:times.length,deterministic:true,source_fidelity:true,counts_match_independent_sql:true};
  }
  if(row.arms.full.status==='ok'&&row.arms.compact.status==='ok')row.additional_records=row.arms.compact.selected_records-row.arms.full.selected_records;
  results.push(row);console.log(country+' '+budget+' '+JSON.stringify(Object.fromEntries(Object.entries(row.arms).map(([k,v])=>[k,v.status==='ok'?v.selected_records:v.status]))));
 }
 const report={format:'tacitus-comparison-benchmark/1',run_at:new Date().toISOString(),compiler_sha256:createHash('sha256').update(await readFile(new URL('../cloudflare/comparison.mjs',import.meta.url))).digest('hex'),runtime:process.version,platform:process.platform,database_records:db.prepare('SELECT count(*) AS n FROM events').get().n,method:'Same full read-only SQLite snapshot; six developer-visible period comparisons, three byte budgets, full vs compact representation. One warm-up and three measured repeated compilations per successful arm. Refusals are recorded, not replaced. Counts independently checked with SQL; every retained field checked against the source record.',cases:results,limitations:['Byte-size and selected-record coverage, not token cost, model answer quality, causality or diplomatic outcomes.','Cases are developer-visible, not a held-out evaluation.','Three measured repetitions give descriptive p50/p95 only; host timing is not Cloudflare latency.','More records is not proof of greater relevance; compact mode omits fields explicitly.']};
 await writeFile(output,JSON.stringify(report,null,2)+'\n');
 console.log('Saved '+results.length+' paired packing cases to '+output);
}finally{db.close();}

