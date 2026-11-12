#!/usr/bin/env node
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {performance} from 'node:perf_hooks';
import {compileDocumentContext} from '../cloudflare/document-context.mjs';
const output=process.argv[2];if(!output)throw Error('Usage: node scripts/benchmark_document_context.mjs new-report.json');
const model=JSON.parse(await readFile(new URL('../data/semantic-documents/unsc-2254.json',import.meta.url),'utf8')),rows=[];
for(const task of Object.keys(model.tasks))for(const budget of [4000,8000,12000,16000]){
 const times=[];let result,refusal;
 for(let i=0;i<6;i++){
  const start=performance.now();try{
   const next=await compileDocumentContext(model,{task,budget});
   if(result&&next.payload!==result.payload)throw Error('Non-deterministic output');result=next;
   if(i)times.push(performance.now()-start);
  }catch(e){if(!e.message.toLowerCase().includes('budget'))throw e;refusal=e.message;break;}
 }
 if(refusal){rows.push({task,budget,status:'refused',reason:refusal});continue;}
 for(const span of result.packet.spans)if(model.document.text.slice(span.start,span.end)!==span.quote)throw Error('Quote mismatch');
 for(const claim of result.packet.assertions)for(const id of [...claim.evidence_span_ids,...claim.required_context_span_ids])if(!result.packet.spans.some(s=>s.id===id))throw Error('Context dependency missing');
 const inline={...result.packet,format:'tacitus-semantic-inline-evidence/1',assertions:result.packet.assertions.map(a=>({...a,evidence:a.evidence_span_ids.map(id=>result.packet.spans.find(s=>s.id===id)),required_context:a.required_context_span_ids.map(id=>result.packet.spans.find(s=>s.id===id))}))};
 delete inline.spans;
 const sorted=[...times].sort((a,b)=>a-b),inlineBytes=Buffer.byteLength(JSON.stringify(inline));
 rows.push({task,budget,status:'ok',selected_assertions:result.receipt.selected_assertions,unique_passages:result.receipt.unique_evidence_spans,payload_bytes:result.receipt.payload_bytes,inline_evidence_variant_bytes:inlineBytes,shared_span_bytes_avoided:inlineBytes-result.receipt.payload_bytes,deterministic:true,exact_spans:true,required_context_retained:true,measured_runs:5,p50_ms:sorted[2],p95_ms:sorted[4],payload_sha256:result.receipt.payload_sha256});
}
const report={format:'tacitus-semantic-benchmark/1',run_at:new Date().toISOString(),runtime:process.version,source_text_sha256:model.document.text_sha256,compiler_sha256:createHash('sha256').update(await readFile(new URL('../cloudflare/document-context.mjs',import.meta.url))).digest('hex'),method:'One cited example, four explicit task profiles, four byte budgets; one warm-up and five measured repeated compilations per successful case. Exact spans, complete required-context dependencies and deterministic bytes checked. A declared inline-evidence representation retains the same selected assertions and evidence but repeats shared source passages per assertion.',cases:rows,limitations:['Developer-visible structural/packing fixture; not a held-out semantic-extraction benchmark.','Curated assertion drafts remain unreviewed. Local pasted text uses separate lexical proposals.','Byte differences compare declared JSON representations, not source-only text versus a packet.','No model generation, token measurements, answer-quality, relevance or cost improvement is inferred.','Host runtime measurements do not establish Cloudflare or model latency.']};
await writeFile(output,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({cases:rows.length,successful:rows.filter(r=>r.status==='ok').length,explicit_refusals:rows.filter(r=>r.status==='refused').length,governance:rows.find(r=>r.task==='governance'&&r.budget===16000)}));

