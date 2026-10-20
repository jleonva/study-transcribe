// Run with NODE_PATH pointing to a local jsdom installation.
const fs=require('fs');const assert=require('assert');const {JSDOM}=require('jsdom');
const source=fs.readFileSync(process.argv[2],'utf8');
const dom=new JSDOM(source,{runScripts:'dangerously',url:'https://offline-review.invalid/',beforeParse(w){w.URL.createObjectURL=()=> 'blob:test';w.URL.revokeObjectURL=()=>{};w.HTMLAnchorElement.prototype.click=function(){w.__download=this.download}}});
const w=dom.window,d=w.document;
assert.equal(d.querySelectorAll('article').length,15,'source sample must retain 15 slots');
assert(d.querySelectorAll('.katex').length>=10,'at least 10 equations must render');
const select=d.querySelector('article select');select.value='correct';select.dispatchEvent(new w.Event('change'));
assert(Object.values(JSON.parse(w.localStorage.getItem('math-pilot-review-v1'))).some(r=>r.status==='correct'));
const note=d.querySelector('textarea');note.value='test review';note.dispatchEvent(new w.Event('input'));
assert(w.localStorage.getItem('math-pilot-review-v1').includes('test review'));
d.getElementById('filter').value='correct';d.getElementById('filter').dispatchEvent(new w.Event('input'));assert.equal(d.querySelectorAll('article').length,1);
d.getElementById('filter').value='';d.getElementById('search').value='zzzz-no-match';d.getElementById('search').dispatchEvent(new w.Event('input'));assert.equal(d.querySelectorAll('article').length,0);
d.getElementById('export').click();assert.equal(w.__download,'math-pilot-review.json');
assert(!d.querySelector('script[src],link[rel=stylesheet]'),'no external runtime dependencies');
const chapter=d.querySelector('#chapters details');assert(chapter);chapter.open=true;chapter.dispatchEvent(new w.Event('toggle'));
assert(chapter.querySelector('.katex'),'chapter formulas render');
assert(chapter.querySelector('img[src^="data:"]'),'chapter figures embedded offline');
for(const other of d.querySelectorAll('#chapters details')){other.open=true;other.dispatchEvent(new w.Event('toggle'));assert(other.querySelector('.katex'),'each chapter/comparison page has rendered mathematics')}
console.log('PASS: 15 slots, equation rendering, status, notes, persistence, filters, search, export, offline assets, complete chapter reader');w.close();
