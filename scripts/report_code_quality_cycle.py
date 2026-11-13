"""Report a closed cycle only; never dispatch, tune, replace, or rescore answers."""
from collections import Counter,defaultdict
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/phase67-gates/code-quality-track'

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def cell(value):return str(value).replace('|','\\|').replace('\r',' ').replace('\n',' ')

def main():
    state=read(OUT/'final-cycle-state.json')
    if state.get('status')!='closed' or not state.get('complete'):raise SystemExit('No report access before complete cycle closure')
    destination=OUT/'final-delivery-report.json'
    if destination.exists():raise SystemExit('Preserve the first completed report')
    summary=read(OUT/'final-cycle-summary.json')
    questions={q['id']:q for q in read(OUT/'heldout.questions.sealed.json')}
    heldout=[]
    for index in (1,2,3):
        heldout.extend(dict(row,run=index) for row in read(OUT/f'final-heldout-run{index}-scored.json'))
    by_category=defaultdict(lambda:dict(correct=0,total=0))
    by_graph=defaultdict(lambda:dict(correct=0,total=0))
    misses=defaultdict(list);invalid=[];verified=[];limited_operations=0
    citation_episodes=0;identity_valid_citation_episodes=0;uncertain_citation_episodes=0
    pattern=re.compile(r'([\w.-]+)/entity:((?:entity:)?[0-9a-f]{64})')
    for row in heldout:
        success=bool(row['markers_found']);question=questions[row['question_id']]
        untracked=any(call['success'] and any(call['tool'].endswith(op) for op in ('compile_task_packet','get_architecture_context','analyze_cross_graphs'))
                      for call in row['per_call'])
        limited_operations+=int(untracked)
        for table,key in [(by_category,question['category']),(by_graph,question['graph'])]:
            table[key]['total']+=1;table[key]['correct']+=int(success)
        if not success:misses[row['question_id']].append(dict(run=row['run'],classification=row['coverage_classification'],
            marker=row['markers'][0],source=row['target_source'],span=row['target_span'],definition_line_returned=row['definition_line_returned'],
            untracked_operation_delivery=untracked))
        verified.extend(row['verified_target_source']);invalid.extend(row['invalid_target_source'])
        citations=pattern.findall(row['answer'])
        if citations:
            citation_episodes+=1
            ids={c['entity_id'] for call in row['per_call'] for c in call.get('coverage',[])}
            ids|={eid for call in row['per_call'] for eid in call.get('supplemental_entities',[])}
            matches=[label==row['graph'] and (eid if eid.startswith('entity:') else 'entity:'+eid) in ids for label,eid in citations]
            identity_valid_citation_episodes+=int(any(matches))
            uncertain_citation_episodes+=int(not all(matches))
    classes=Counter(row['coverage_classification'] for row in heldout if not row['markers_found'])
    report=dict(official_summary=summary,heldout_by_category=dict(by_category),heldout_by_graph=dict(by_graph),
        miss_classes=dict(classes),misses_by_question=dict(misses),verified_target_ranges=len(verified),invalid_target_ranges=len(invalid),
        heldout_episodes_with_definition_line=sum(row['definition_line_returned'] for row in heldout),
        heldout_episodes_with_entity_citations=citation_episodes,heldout_episodes_with_identity_valid_citations=identity_valid_citation_episodes,
        heldout_episodes_with_unverified_citation_identities=uncertain_citation_episodes,
        heldout_episodes_using_operations_without_source_coverage=limited_operations,
        citation_scope='Supplementary identity check against delivered canonical metadata; no answer rescore or substantive claim-entailment judgement.')
    with destination.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2,ensure_ascii=False)
    lines=['\n## Closed-cycle results and delivery evidence\n',
        '| Set | Run | Correct / total | Tool calls/question | Errors | Wrong graph | Withheld | Cost |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for row in summary['runs']:
        lines.append(f"| {row['group']} | {row['run']} | {row['correct']}/{row['total']} | {row['calls']/row['total']:.2f} | {row['tool_errors']} | {row['wrong_graph']} | {row['withheld']} | ${row['cost_usd']:.7f} |")
    lines+=['',f"Registered verdict: **{'PASS' if summary['passed'] else 'FAIL'}**. Development **{summary['development_correct']}/15**; held-out **{summary['heldout_correct']}/75**. Mean tool calls **{summary['calls_per_question']:.2f}**. Cycle cost **${summary['cost_usd']:.7f}**. No replacement run or product tuning follows.",
        '', '| Held-out stratum | Correct / total |','|---|---:|']
    for kind,data in [*by_category.items(),*by_graph.items()]:lines.append(f"| {kind} | {data['correct']}/{data['total']} |")
    lines+=['',f"Coverage classes for held-out misses: `{json.dumps(dict(classes),sort_keys=True)}`. Independently verified target source ranges: **{len(verified)}**; invalid hashes/provenance: **{len(invalid)}**. The defining source line was returned in **{report['heldout_episodes_with_definition_line']}/75** episodes. Metadata/card retrieval is not counted as source-body delivery.",
        '',f"Coverage scope: the frozen recorder captures search/content coverage and supplemental constant-card IDs. Architecture, packet and cross-graph payloads do not supply equivalent range records; {limited_operations}/75 episodes used those operations. An absence classification in such an episode is provisional, not proof the agent never saw the definition in another payload. Positive hash-verified delivery remains positive evidence. These limits do not rescore answers.",
        '',f"Supplementary citation check: {citation_episodes}/75 episodes contain entity citation handles; {identity_valid_citation_episodes}/75 have at least one identity present in delivered scoped metadata; {uncertain_citation_episodes}/75 contain at least one identity not verified by the bounded records. This check normalizes the `entity:` prefix and is not proof of literal handle copying or substantive claim support. It does not alter the registered marker scores."]
    if misses:
        lines+=['','### Held-out misses (all original rows retained)','',
            '| Question | Expected defining identifier / source | Missed runs and coverage class |','|---|---|---|']
        for qid,items in sorted(misses.items()):
            first=items[0];description=questions[qid]['question']
            runs='; '.join(f"run {m['run']}: {m['classification']} (definition line {'returned' if m['definition_line_returned'] else 'not verified returned'}"+
                          ('; other operation delivery untracked' if m['untracked_operation_delivery'] else '')+')' for m in items)
            lines.append(f"| {cell(qid+': '+description)} | `{cell(first['marker'])}`; `{cell(first['source'])}:{first['span'][0]}` | {cell(runs)} |")
    lines+=['','The private seal was created before product changes; its key was first opened after all six raw batches completed. All raw, scored, first failed and cost files remain separate. The invalid development A/B remains disclosed and P3 remains removed. Wave 4 remains closed/passed at **12/15**. No merge or push was performed.']
    text='\n'.join(lines)+'\n'
    for path in (ROOT/'reports/PHASE67_CODE_QUALITY_TRACK.md',ROOT/'reports/PHASE67_WAVE4_GATE.md'):
        with path.open('a',encoding='utf-8') as f:f.write(text)
    print(json.dumps(dict(report=str(destination),heldout=summary['heldout_correct'],development=summary['development_correct'],
                          miss_classes=dict(classes),verified_ranges=len(verified),invalid_ranges=len(invalid))))
if __name__=='__main__':main()
