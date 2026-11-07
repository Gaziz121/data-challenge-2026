// DOM rendering regression tests; fixtures are not DEV labels or provider judgments.
const assert = require('node:assert/strict');
const {renderResult, responseText} = require('../web/app.js');
const transcript = require('../tools/dev_review/transcript.js');
const checklist = require('../src/cqa/checklists/official-v1.json');

class Element {
  constructor(tag, doc) {this.tagName = tag; this.ownerDocument = doc; this.children = []; this.dataset = {}; this.textContent = '';}
  append(...children) {this.children.push(...children);}
  replaceChildren(...children) {this.children = children;}
}
const doc = {createElement: tag => new Element(tag, doc), createDocumentFragment: () => new Element('fragment', doc)};
const walk = node => [node, ...node.children.flatMap(walk)];
const texts = node => walk(node).map(n => n.textContent).join('\n');
const container = doc.createElement('div'), summary = doc.createElement('p');
const result = {run: {is_mock:true,provider:'mock',model_returned:'fixture',latency_ms:0,usage:{}},
  score:{total_score:'83.33',critical_violation:false,criteria:checklist.criteria.map(c=>({criterion_id:c.criterion_id,
    base_weight:c.weight,effective_weight:'sent-from-backend',earned_points:'sent-from-backend'}))},
  checklist,status:'mock_only',model_evaluation:{decisions:checklist.criteria.map(c=>({criterion_id:c.criterion_id,
    response:c.criterion_id==='02'?'N/A':c.kind==='discrete'?0:'no',rationale:'fixture rationale',
    na_reason:c.criterion_id==='02'?'fixture allowed condition':null,needs_review:true,review_reason:'fixture review',
    evidence:[{kind:'quote',message_id:'m0001',quote:'<script>literal source</script>',explanation:'fixture reference'}],
    atomic_checks:c.questions.map(q=>({question_id:q.question_id,answer:'unknown',rationale:'fixture atomic',evidence:[]}))}))},
  check_outcomes:[],audit:[],revision_history:[]};
let reference;
renderResult(result,container,summary,r=>reference=r);
assert.equal(walk(container).filter(n=>n.className==='result-card').length,8);
assert.match(summary.textContent,/MOCK FIXTURE/);
assert.match(summary.textContent,/83.33/); // Display the backend total, never derive a total from points.
assert.match(texts(container),/N\/A — not applicable/);
assert.match(texts(container),/N\/A reason: fixture allowed condition/);
assert.match(texts(container),/sent-from-backend/);
assert.match(texts(container),/<script>literal source<\/script>/); // Literal text, no innerHTML parsing.
const evidenceButton = walk(container).find(n=>n.tagName==='button'); evidenceButton.onclick();
assert.equal(reference.message_id,'m0001');
assert.equal(evidenceButton.dataset.startMessageId,'m0001');
result.run.is_mock=false;result.status='needs_review';
renderResult(result,container,summary,()=>{});
assert.match(summary.textContent,/LLM evaluation — semantic accuracy not independently verified/);
assert.doesNotMatch(summary.textContent,/MOCK FIXTURE/);
result.score.total_score=null; renderResult(result,container,summary,()=>{});
assert.match(summary.textContent,/not calculated/);
assert.equal(responseText({response:7},{kind:'discrete',levels:[0,4,7,10]}),'7 / 10');

const raw={transcript:[{speaker:'client',timestamp:'00:00',text:'  Ә\n<literal>',message_id:null},
  {speaker:'operator',timestamp:'00:01',text:'Fictional response',message_id:'source-1'}]};
transcript.render(container,raw);
assert.match(texts(container),/Original message ID: not provided/);
assert.match(texts(container),/Original message ID: source-1/);
assert.match(texts(container),/  Ә\n<literal>/);
const normalized={messages:raw.transcript.map((m,i)=>({source_speaker:m.speaker,timestamp:m.timestamp,text:m.text,
  message_id:`m000${i}`,source_index:i,source_message_id:m.message_id}))};
transcript.render(container,normalized);
const article=walk(container).find(n=>n.id==='message-1');
assert.equal(article.dataset.messageId,'m0001');
assert.match(texts(container),/Original message ID: source-1/);
assert.doesNotMatch(texts(container),/Original message ID: m0001/);
console.log('PASS: eight results, N/A reasons, backend-only totals, mock/LLM labeling, evidence targets, literal source text and shared transcript renderer.');
