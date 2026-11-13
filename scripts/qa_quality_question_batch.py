"""Offline fixture proves blind collection, graph switching, and one-shot output."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'output/phase67-gates/lib-wave4/src')]
import librarian_harness as h

def main():
    opened=[];closed=[];seen=[]
    class FakeHarness:
        def __init__(self,catalog,workdir,scoping,launch,bundles,context,preset,label,wheel,self_check=None):
            assert scoping=='library' and preset=='lead' and context==1048576
            assert self_check is True  # The batch A/B ON arm must reach every Loop.
            self.label=label;self.labels={'fixture-'+label:label};self.context_tokens=context;self.preset=preset
            opened.append((str(workdir),label))
        def close(self):closed.append(self.label)
        def server_for(self,label):return 'fixture'
        def run(self,provider,prompt,server):
            assert 'SEALED-KEY-DO-NOT-READ' not in prompt
            seen.append((self.label,prompt))
            return dict(answer='Offline collection fixture.',tool_text='',graphs_called=[],tool_calls=0,per_call=[],withheld_oversize=0)
    h.Harness=FakeHarness;h.provider_for=lambda model:object()
    with tempfile.TemporaryDirectory(prefix='geo-quality-fixture-') as temp:
        root=Path(temp);questions=root/'fixture-questions.json';out=root/'collected.json'
        questions.write_text(json.dumps([dict(id=f'fixture-{i}',graph='librarian-v2' if i%2==0 else 'ToolSet',
            question=f'Which fixture implementation defines operation number {i}? Cite the source.') for i in range(25)]))
        args=argparse.Namespace(question_file=questions,resume=False,model='offline',catalog=root/'catalog.sqlite',
            scoping='library',launch='uvx',bundles='off',context_tokens=1048576,preset='lead',wheel=root/'wheel.whl',self_check='on')
        h.question_batch(args,out)
        rows=json.loads(out.read_text())
        assert len(rows)==len(seen)==len(opened)==len(closed)==25
        assert len({path for path,label in opened})==25
        assert all('markers' not in row and 'markers_found' not in row for row in rows)
        try:h.question_batch(args,out)
        except SystemExit:pass
        else:raise AssertionError('A second batch must be refused')
        assert len(seen)==25
    print(json.dumps(dict(passed=True,fixture_questions=25,paid_provider_calls=0,graph_switches=25)))
if __name__=='__main__':main()
