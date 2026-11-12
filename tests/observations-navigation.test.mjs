import assert from 'node:assert/strict';
import test from 'node:test';
import { decodeNavigation, encodeNavigation, networkNeighborhood, lensNeighborhood, reproductionRecipe } from '../src/syria_analysis/web/observations-navigation.js';

test('URL navigation round-trips public-data scope without private text', () => {
  const state = decodeNavigation('?country=SY&from=2024&to=2025&type=1&precision=1&actor=SDF&view=lenses&lens=skos&collection=index&nodes=250&event=ucdp-ged:26.1:123&scope=selected', ['SY','LB']).value;
  assert.equal(state.actor, 'sdf');
  const encoded = encodeNavigation({...state, question:'Private question', notes:'Private notes', credential:'Do not copy'});
  assert.deepEqual(decodeNavigation(encoded, ['SY','LB']).value, state);
  for (const word of ['Private','question','notes','credential']) assert.equal(encoded.includes(word), false);
  assert.ok(encoded.length < 1024);
});

test('invalid, duplicate, oversized and cross-origin-ish filters are bounded and ignored', () => {
  const parsed = decodeNavigation('?country=US&from=1800&to=NaN&type=9&precision=0&view=javascript:alert(1)&actor='+encodeURIComponent('x'.repeat(201))+'&event=https://evil.test/row&indicator=../../secret&country=SY', ['SY','LB']);
  assert.equal(parsed.value.country, 'SY');
  assert.equal(parsed.value.from, 2020);
  assert.equal(parsed.value.to, 2025);
  assert.equal(parsed.value.actor, '');
  assert.equal(parsed.value.selectedId, '');
  assert.equal(parsed.value.indicatorCode, 'SP.POP.TOTL');
  assert.ok(parsed.ignored.length >= 8);
  assert.deepEqual(decodeNavigation('x'.repeat(4097)).value, decodeNavigation('').value);
  assert.equal(decodeNavigation('?actor=line%0Abreak').value.actor, '');
  assert.equal(decodeNavigation('?from=2025&to=2024').ignored.includes('reversed interval'), true);
});

test('an empty selected-record scope never silently widens to a query export', () => {
  const parsed = decodeNavigation('?scope=selected');
  assert.equal(parsed.value.scope, 'selected');
  assert.equal(parsed.value.selectedId, '');
  assert.ok(parsed.ignored.includes('selected scope without a record'));
});

test('network navigation retains actual one-hop edges and explicit full counts', () => {
  const pairs = Array.from({length:22},(_,i)=>({names:['A',`side${i}`],count:22-i}));
  pairs.push({names:['B','C'],count:50});
  const graph = networkNeighborhood(pairs, 'A', 6);
  assert.equal(graph.names.length,6);
  assert.equal(graph.connectedNames,23);
  assert.equal(graph.totalNames,25);
  assert.equal(graph.pairs.every(pair=>pair.names.includes('A')),true);
  assert.equal(networkNeighborhood(pairs,'A',18).names.length,18);
  assert.equal(networkNeighborhood(pairs,'A',999).names.length,6);
  assert.equal(networkNeighborhood([], 'missing').focus,'');
  assert.deepEqual(networkNeighborhood(pairs,'A',6),networkNeighborhood(pairs,'A',6));
});

test('graph record neighbourhoods keep the selected identity and prefer its recorded group', () => {
  const rows = Array.from({length:300},(_,i)=>({id:`r${i}`,date_start:`2024-01-${String(i%28+1).padStart(2,'0')}`,group:i%2?'odd':'even'}));
  const before=structuredClone(rows), selected=rows[201];
  const chosen = lensNeighborhood(rows,selected,60,row=>row.group);
  assert.equal(chosen.length,60);
  assert.equal(chosen[0].id,selected.id);
  assert.equal(chosen.every(row=>row.group===selected.group),true);
  assert.deepEqual(rows,before);
  assert.equal(lensNeighborhood(rows,null,1000).length,300);
  assert.equal(lensNeighborhood(rows,null,999).length,60);
});

test('reproduction recipe preserves snapshot IDs and qualifies unsupported CLI selection modes', () => {
  const state=decodeNavigation('?country=SY&from=2024&to=2025&actor='+encodeURIComponent("a'$(touch example)")+'&search=city&scope=both').value;
  const result=reproductionRecipe(state,[{id:'provider',sha256:'a'.repeat(64)}],'https://example.test/observations/?country=SY');
  assert.ok(result.includes("--actor 'a'\\''$(touch example)'"));
  assert.ok(result.includes('provider: '+'a'.repeat(64)));
  assert.ok(result.includes('does not reproduce those extra selections'));
  assert.ok(result.includes('ascending date and ID order'));
  assert.ok(!result.includes('Private question'));
  const annual=reproductionRecipe({...state,scope:'indicators',indicatorCode:'NY.GDP.MKTP.KD'},[],'https://example.test/');
  assert.match(annual,/--indicator 'NY.GDP.MKTP.KD' --from-year 1900 --to-year 2100/);
  assert.equal(annual.includes('--actor'),false);
});
