const {test}=require('node:test');
const assert=require('node:assert/strict');
const engine=require('./engine.js');
test('incomplete discoveries and unacknowledged review cannot export',()=>{
  assert.throws(()=>engine.receipt({},'test'),/Complete all rooms/);
  assert.throws(()=>engine.receipt({condition:true,attribution:true,time:true},'test'),/Complete all rooms/);
});
test('export keeps exact source spans, missing evidence and separate analyst notes',()=>{
  const record=engine.receipt({condition:true,attribution:true,time:true,review:true},'test','An analyst interpretation.');
  const quote=record.evidence[0],source=record.sources.find(s=>s.id===quote.source_id);
  assert.equal(source.text.slice(quote.start,quote.end),quote.quote);
  assert.match(quote.quote,/if the inspection was completed/);
  assert.equal(record.analyst_notes,'An analyst interpretation.');
  assert.equal(record.synthetic,true);
  assert.match(record.finding,/not confirmed/);
  assert.equal(record.omissions.length,3);
});
test('quotation matching rejects empty or invented evidence',()=>{
  assert.equal(engine.validateQuote(engine.sources[0],''),false);
  assert.equal(engine.validateQuote(engine.sources[0],'The harbor is open.'),false);
  assert.equal(engine.validateQuote(engine.sources[0],engine.evidenceQuote),true);
});
