#!/usr/bin/env node
import {DatabaseSync} from 'node:sqlite';
import {performance} from 'node:perf_hooks';
import {writeFile,mkdir} from 'node:fs/promises';
import {sqliteBinding} from '../cloudflare/local-api.mjs';
import {compileBrief,parseOptions,predicate} from '../cloudflare/briefing.mjs';
const dbPath=process.argv[2],out=process.argv[3];
if(!dbPath||!out)throw Error('Usage: node scripts/benchmark_briefing.mjs database output.json');
const db=new DatabaseSync(dbPath,{readOnly:true}),binding=sqliteBinding(db);
const cases=[['SY',2014,2016],['IQ',2014,2017],['LB',2006,2006],['YE',2015,2020],['JO',2000,2025],['SY',2000,2001]];
const percentile=(a,p)=>[...a].sort((x,y)=>x-y)[Math.min(a.length-1,Math.ceil(a.length*p)-1)];
const rows=[],packing=[];
try{
 for(const [country,from,to]of cases){
  const o=parseOptions(new URLSearchParams({country,from,to})),p=predicate(o);
  const indexed=db.prepare('SELECT count(*) AS records FROM events WHERE '+p.sql);
  const scan=db.prepare('SELECT count(*) AS records FROM events NOT INDEXED WHERE '+p.sql);
  const legacy=db.prepare('SELECT count(*) AS records FROM events INDEXED BY events_country_date WHERE '+p.sql);
  const timings={indexed:[],legacy:[],scan:[]};let expected;
  for(let i=0;i<21;i++){
   for(const mode of [ ['indexed','legacy','scan'],['scan','indexed','legacy'],['legacy','scan','indexed'] ][i%3]){
    const start=performance.now(),r=(mode==='scan'?scan:mode==='legacy'?legacy:indexed).get(...p.args).records,ms=performance.now()-start;
    if(expected!==undefined&&r!==expected)throw Error('Query result mismatch');expected=r;
    if(i)timings[mode].push(ms);
   }
  }
  rows.push({country,from,to,records:expected,repetitions_per_arm:20,indexed_p50_ms:percentile(timings.indexed,.5),indexed_p95_ms:percentile(timings.indexed,.95),scan_p50_ms:percentile(timings.scan,.5),scan_p95_ms:percentile(timings.scan,.95),legacy_p50_ms:percentile(timings.legacy,.5),legacy_p95_ms:percentile(timings.legacy,.95),same_results:true,query_plan:db.prepare('EXPLAIN QUERY PLAN SELECT count(*) FROM events WHERE '+p.sql).all(...p.args).map(x=>x.detail)});
  for(const budget of [8000,16000,32000]){
   const start=performance.now();const result=await compileBrief(binding,{...o,budget});const ms=performance.now()-start;
   const repeat=await compileBrief(binding,{...o,budget});
   if(result.payload!==repeat.payload||result.receipt.payload_bytes>budget)throw Error('Determinism/budget failure');
   for(const record of result.packet.evidence){const original=JSON.parse(db.prepare('SELECT record_json FROM events WHERE id=?').get(record.id).record_json);if(JSON.stringify(original)!==JSON.stringify(record))throw Error('Source fidelity failure');}
   packing.push({country,from,to,budget,payload_bytes:result.receipt.payload_bytes,selected:result.receipt.selected_records,matched:result.receipt.matched_records,elapsed_ms:ms,deterministic:true,exact_record_fidelity:true});
  }
 }
 const state=Object.fromEntries(db.prepare('SELECT key,value FROM research_meta').all().map(r=>[r.key,JSON.parse(r.value)]));
 const report={format:'tacitus-briefing-benchmark/1',run_at:new Date().toISOString(),runtime:process.version,platform:process.platform,architecture:process.arch,snapshot_id:state.snapshot.id,counts:state.counts,method:'Read-only SQLite. One warm-up, 20 measured repetitions per arm per case, rotating covering-index/legacy-index/NOT INDEXED execution order. Same prepared count query, inputs and full database. Warm OS cache. Compilation measured separately.',query_cases:rows,packing_cases:packing,limitations:['Fixed developer-visible cases; structural/performance checks, not held-out diplomatic evaluation.','SQLite timings on this host are not Cloudflare latency or model speed.','No model generation, token measurements, answer-quality evaluation or monetary savings.','Compilation timing is one observation per budget/case; query p50/p95 are descriptive over 20 repetitions.']};
 await writeFile(out,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({query_cases:rows.length,packing_cases:packing.length,all_equal:true,all_deterministic:true,all_within_budget:true,output:out}));
}finally{db.close();}

