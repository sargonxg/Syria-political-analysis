import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {compileDocumentContext,validateDocument,proposeDocument,hashText} from './document-context.mjs';
const fixture=JSON.parse(await readFile(new URL('../data/semantic-documents/unsc-2254.json',import.meta.url),'utf8'));
test('curated spans resolve exactly; all profile outputs are deterministic and budgeted',async()=>{
 for(const task of Object.keys(fixture.tasks)){
  const a=await compileDocumentContext(fixture,{task,budget:16000}),b=await compileDocumentContext(fixture,{task,budget:16000});
  assert.equal(a.payload,b.payload);assert.equal(Buffer.byteLength(a.payload),a.receipt.payload_bytes);assert.equal(await hashText(a.payload),a.receipt.payload_sha256);
  for(const s of a.packet.spans)assert.equal(fixture.document.text.slice(s.start,s.end),s.quote);
  assert.equal(a.packet.analyst_assessment,null);assert.ok(a.packet.assertions.every(a=>!a.human_review_recorded));assert.ok(a.receipt.payload_bytes<=16000);
 }
});
test('governance deduplicates the shared source paragraph; ceasefire retains scope exceptions',async()=>{
 const g=await compileDocumentContext(fixture,{task:'governance',budget:16000});assert.equal(g.packet.assertions.length,4);assert.equal(g.packet.spans.length,1);
 const c=await compileDocumentContext(fixture,{task:'ceasefire',budget:16000});assert.deepEqual(c.packet.spans.map(s=>s.id),['op-5','op-8']);
 assert.match(c.markdown,/Required context: Operative paragraph 8/);assert.match(c.markdown,/will not apply/);
});
test('altered source bytes, quote locators, domain/range and invented review fail',async()=>{
 for(const mutate of [
 m=>m.document.text+='changed',
 m=>m.spans[0].start++,
 m=>m.assertions[0].predicate='convenes',
 m=>m.assertions[0].human_review_recorded=true,
 m=>m.assertions[0].concept_ids.push('invented'),
 m=>m.entities.push(m.entities[0])
 ]){const m=structuredClone(fixture);mutate(m);await assert.rejects(()=>validateDocument(m));}
});
test('budget failure never shortens a condition or exports a partial assertion',async()=>{
 await assert.rejects(()=>compileDocumentContext(fixture,{task:'ceasefire',budget:2048}),/budget/);
 for(const budget of [6000,8000,12000]){
  const r=await compileDocumentContext(fixture,{task:'all',budget});
  assert.ok(r.receipt.payload_bytes<=budget);
  for(const a of r.packet.assertions)for(const id of [...a.evidence_span_ids,...a.required_context_span_ids])assert.ok(r.packet.spans.some(s=>s.id===id));
 }
 await assert.rejects(()=>compileDocumentContext(fixture,{task:'prediction',budget:16000}),/Unknown task/);
});
test('JSON-LD reifies source assertions and emits no bare political relation',async()=>{
 const r=await compileDocumentContext(fixture,{task:'all',budget:16000}),nodes=r.graph['@graph'];
 assert.equal(nodes.filter(n=>n['@type']==='rdf:Statement').length,6);
 assert.ok(nodes.filter(n=>n['@type']==='rdf:Statement').every(n=>n['prov:wasDerivedFrom'].length&&n['policy:reviewState']==='needs_source_check'));
 assert.ok(nodes.every(n=>!Object.hasOwn(n,'policy:requests')&&!Object.hasOwn(n,'policy:expresses_support_for')));
});
test('local text yields literal, unreviewed candidates with Unicode-correct offsets',async()=>{
 const text='🕊 A local source.\n\nThe office requests consultation if all parties agree.\n\nThere is no implementation evidence.';
 const m=await proposeDocument(text);assert.equal(m.assertions.length,1);assert.equal(m.document.issuer,null);
 assert.equal(text.slice(m.spans[0].start,m.spans[0].end),m.spans[0].quote);
 assert.equal(m.assertions[0].predicate,'contains_expression');
 const r=await compileDocumentContext(m,{task:'all',budget:8000});assert.match(r.payload,/if all parties agree/);assert.equal(r.graph['@context'].policy,'urn:tacitus:local-text:');
 await assert.rejects(()=>proposeDocument('x'.repeat(32769)),/32/);
 const empty=await proposeDocument('A plain reading note.');assert.equal(empty.assertions.length,0);
 const e=await compileDocumentContext(empty,{task:'all',budget:4000});assert.equal(e.packet.assertions.length,0);
});

