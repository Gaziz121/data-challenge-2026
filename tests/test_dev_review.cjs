// Export/resume fixtures are fictional test records, never dataset assessments.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const api = require('../tools/dev_review/viewer.js');
const rubric = JSON.parse(fs.readFileSync(path.join(__dirname, '../tools/dev_review/rubric.json'), 'utf8'));
const data = {source: {path: 'fixture-only.json', sha256: 'fixture-sha'}, rubric, rubric_sha256: 'fixture-rubric',
  records: [{conversation_id: 'fixture-only', language: 'KZ', channel: 'agent chat', transcript: [
    {speaker:'client', text:'  Ә і ң\n<literal> & "quote"', timestamp:'00:00'},
    {speaker:'operator', text:'Fictional test message', timestamp:'00:01', message_id:'fixture-msg-id'}]}]};
const a = api.newSession('reviewer-a'), b = api.newSession('reviewer-b');
assert.throws(() => api.bundle(data, a), /No human entries/);
a.assessments['fixture-only'] = {updated_at:new Date().toISOString(), criteria:Object.fromEntries(rubric.criteria.map(c => [c.id, api.blank()]))};
a.assessments['fixture-only'].criteria['01'] = {response:'no', justification:'=formula, "quoted"\nӘ', evidence_indexes:'1, 0', scope_note:'fixture only'};
a.assessments['fixture-only'].criteria['02'].response = 'N/A';
a.assessments['fixture-only'].criteria['04'].response = 0;
const saved = api.bundle(data, a);
assert.equal(saved.label_source, 'team_human');
assert.equal(saved.official_ground_truth, false);
assert.equal(saved.assessments[0].status, 'draft');
assert.equal(saved.assessments[0].criteria.length, 8);
assert.equal(saved.assessments[0].criteria[2].response, null);
assert.equal(saved.assessments[0].criteria[3].response, 0);
assert.equal(saved.assessments[0].criteria[0].evidence[0].original_message_id, 'fixture-msg-id');
assert.equal(saved.assessments[0].criteria[0].evidence[1].text, data.records[0].transcript[0].text);
assert.deepEqual(api.bundle(data, api.importBundle(data, saved)).assessments, saved.assessments);
assert.equal(Object.keys(b.assessments).length, 0);
assert.equal(api.csv(saved).split('\r\n').length, 10); // Header + eight rows + trailing line ending.
assert.ok(api.csv(saved).includes('"\'=formula, ""quoted""\nӘ"'));
assert.deepEqual(api.indexes('0, 1, 0', 2), [0, 1]);
for (const bad of ['-1','2','1.5','01','0,','word']) assert.throws(() => api.indexes(bad, 2));
for (const change of [
  x => x.label_source = 'official_gt',
  x => x.official_ground_truth = true,
  x => x.dataset.sha256 = 'other',
  x => x.rubric_sha256 = 'other',
  x => x.assessments.push(x.assessments[0]),
  x => x.assessments[0].criteria[0].response = 'N/A',
  x => x.assessments[0].criteria[0].evidence[0].text = 'modified',
  x => x.assessments[0].criteria[0].evidence[0].transcript_index = 42,
]) {const changed = JSON.parse(JSON.stringify(saved)); change(changed); assert.throws(() => api.importBundle(data, changed));}
a.assessments['fixture-only'].criteria['01'].evidence_indexes = '2';
assert.throws(() => api.bundle(data, a), /fixture-only, criterion 01/);
console.log('PASS: blank independent reviews, allowed responses, exact evidence, JSON resume, CSV escaping, invalid import rejection (fictional fixtures only).');
