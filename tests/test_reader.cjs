// node tests/test_reader.cjs /path/to/existing/node_modules
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {JSDOM}=require(path.join(path.resolve(process.argv[2]),'jsdom'));
const book={title:'<script>bad</script>',book_id:'fixture',revision:1,credit:'',passages:[{text:'😀 hello',speaker:'Narrator',chapter:'One',start:0,end:1,words:[{from:3,to:8,start:.2,end:.7}]},{text:'Another line.',speaker:'Narrator',chapter:'Two',start:1,end:2,words:[]}]};
const html=fs.readFileSync(path.join(__dirname,'../reader.html'),'utf8').replace('/*BOOK_DATA*/null',JSON.stringify(book).replaceAll('<','\\u003c'));
const dom=new JSDOM(html,{runScripts:'dangerously',url:'https://example.test',beforeParse(w){w.requestAnimationFrame=()=>0;w.HTMLElement.prototype.scrollIntoView=()=>{};w.URL.createObjectURL=()=> 'blob:fixture';w.URL.revokeObjectURL=()=>{}}});
try{const d=dom.window.document,a=d.querySelector('audio');assert.equal(d.querySelector('h1').textContent,book.title);assert.equal(d.querySelectorAll('main script').length,0);
Object.defineProperty(d.getElementById('file'),'files',{value:[{}]});d.getElementById('file').dispatchEvent(new dom.window.Event('change'));assert.equal(a.src,'blob:fixture');
a.currentTime=.3;a.dispatchEvent(new dom.window.Event('timeupdate'));assert.equal(d.querySelector('mark').textContent,'hello');assert.equal(d.querySelector('.active').textContent,'😀 hello');
a.currentTime=1.2;a.dispatchEvent(new dom.window.Event('seeked'));assert.equal(d.querySelector('mark'),null);assert.equal(d.querySelector('.active').textContent,'Another line.');
d.querySelector('main p').click();assert.equal(a.currentTime,0);const speed=d.getElementById('speed');speed.value='1.5';speed.dispatchEvent(new dom.window.Event('change'));assert.equal(a.playbackRate,1.5);
assert.equal(d.querySelectorAll('#chapters option').length,2);console.log('PASS: local audio selection, source escaping, UTF-16 word highlight, passage fallback, seeking, playback speed, chapters');}finally{dom.window.close()}
