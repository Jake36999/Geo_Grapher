"""Repair opened v1 as development data; never read held-out v2."""
import ast
import json
from pathlib import Path
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'src'),str(Path(__file__).resolve().parent)]
from offline_graphs import FrozenGraphs

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'output/phase67-gates/code-quality-track'
DEST=ROOT/'data/eval/code-research'
CATALOG=Path('D:/Librarian_V2/tmp/geo-grapher-wave4-continuation-stores/catalog.sqlite')

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def write(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,ensure_ascii=False)

def main():
    DEST.mkdir(parents=True,exist_ok=True)
    if (DEST/'development30.json').exists():raise SystemExit('Preserve the first repaired development set')
    questions=read(OLD/'heldout.questions.sealed.json');oldkeys={x['id']:x for x in read(OLD/'heldout.answers.sealed.json')}
    records={q['id']:[] for q in questions};seen=set();calls=0
    for run in (1,2,3):
        for row in read(OLD/f'final-heldout-run{run}.json'):
            for call in row['per_call']:
                if not call['tool'].endswith('search_entities'):continue
                calls+=1;args=json.loads(call['arguments']);query=args['query']
                identity=(row['question_id'],row['graph'],query)
                if identity not in seen:seen.add(identity);records[row['question_id']].append(query)
    with FrozenGraphs(CATALOG) as frozen:
        graphs={label:frozen.graph(label) for label in ('librarian-v2','ToolSet')}
        def ids(label,suffix,required=True):
            found=[e.entity_id for e in graphs[label].entities.values() if e.qualified_name.endswith(suffix) and e.kind in {'constant','function','method','class'}]
            if required and not found:raise ValueError('Development definition not found: '+suffix)
            return found
        def entry(qid,label,question,targets,markers,**extra):
            members=[graphs[label].entities[eid] for eid in sorted(set(targets))]
            return dict(id=qid,graph=label,question=question,targets=[e.entity_id for e in members],markers=sorted(set(markers)),
                provenance=[dict(entity_id=e.entity_id,qualified_name=e.qualified_name,path=e.rel_path,start=e.start_line,end=e.end_line) for e in members],**extra)
        reference=[];development=[];repairs=[]
        for q in questions:
            key=oldkeys[q['id']];targets=[key['entity_id']];markers=[key['marker']];question=q['question']
            reference.append(entry(q['id'],q['graph'],question,targets,markers,recorded_queries=records[q['id']],category=q['category']))
            reasons=[]
            if q['id']=='heldout-02':
                targets+=ids(q['graph'],'loop.py._compact_result')+ids(q['graph'],'loop.py.Loop.view')+ids(q['graph'],'loop.py.OLD_RESULT_CHARS')
                markers+=['_compact_result','Loop.view','OLD_RESULT_CHARS']
                reasons.append('Compaction implementation and inseparable history-view/configuration are accepted, rather than only retention constant.')
            if q['id']=='heldout-04':
                question='Which named constant defines the sandbox runner that reads its job from /job/spec.json, imports one module, calls one function and prints a marked JSON line? Cite the source.'
                reasons.append('Repair garbled wording and explicitly ask for the documented constant.')
            if q['id']=='heldout-10':
                question='Which rule identifier rejects create_file_map_v2.py with the -o flag because that script does not support it? Cite the source.'
                targets+=ids(q['graph'],'tool_command_linter.py.rule_r001');markers+=['rule_r001']
                reasons.append('Replace under-specified separator-only prompt using the defining rule function documentation, retaining R001 as an equivalent identifier.')
            if q['id']=='heldout-16':
                targets+=ids(q['graph'],'tool_command_linter.py.R005',required=False);markers+=['R005']
                reasons.append('The requested documented rule ID R005 is equivalent to defining function rule_r005.')
            development.append(entry(q['id'],q['graph'],question,targets,markers,recorded_queries=records[q['id']],
                category=q['category'],original_question=q['question'],original_five=False))
            if reasons:repairs.append(dict(id=q['id'],reasons=reasons,question_changed=question!=q['question'],original_frozen_score_unchanged=True))
        tree=ast.parse((ROOT/'scripts/librarian_harness.py').read_text(encoding='utf-8'))
        original=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CODE_BENCH' for t in n.targets))
        suffixes=[['tools/delegate.py.HELPER_TOOLS'],['tools/delegate.py.delegate','effort.py.Effort'],['clerk.py.run_one'],['mcp_client.py.MAX_EXTERNAL_RESULT'],['loop.py.DEFAULT_CONTEXT_TOKENS']]
        first=[]
        for index,((question,markers),locations) in enumerate(zip(original,suffixes),1):
            targets=[eid for suffix in locations for eid in ids('librarian-v2',suffix,required=False)]
            if not targets:raise ValueError('Original development target unavailable')
            first.append(entry(f'dev-{index:02d}','librarian-v2',question,targets,markers,recorded_queries=[],original_five=True,category='original',legacy_marker_required=True))
        manifest=dict(snapshots=frozen.snapshots,original_count=5,repaired_v1_count=25,recorded_search_calls=calls,
            distinct_agent_queries=len(seen),repairs=repairs,
            scoring_rule='Equivalence markers chosen from defining/implementing code; original five preserve exact legacy marker requirements. Original v1 cycle rows and scores never changed.')
        write(DEST/'v1-frozen-reference.json',dict(manifest=manifest,questions=reference))
        write(DEST/'development30.json',dict(manifest=manifest,questions=first+development))
        write(DEST/'repair-record.json',manifest)
        print(json.dumps(dict(development=30,v1_reference=25,distinct_agent_queries=len(seen),search_calls=calls,repairs=len(repairs))))
if __name__=='__main__':main()
