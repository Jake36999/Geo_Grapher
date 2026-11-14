"""Exercise the actual scoped harness with a scripted provider and no API calls."""
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'output/phase67-gates/lib-wave4/src'))
sys.path.insert(0,str(ROOT/'scripts'))
import librarian_harness as h
from resource_librarian.providers import Provider,Reply,ToolCall
from resource_librarian.registry import REGISTRY

OUT=ROOT/'output/phase67-gates/code-quality-track'

def objects(value):
    if isinstance(value,str):
        try:yield from objects(json.loads(value))
        except ValueError:pass
    elif isinstance(value,dict):
        yield value
        for v in value.values():yield from objects(v)
    elif isinstance(value,list):
        for v in value:yield from objects(v)

class Offline(Provider):
    name='offline-scripted-no-api'
    def __init__(self,names):self.names=names;self.calls=0;self.temperatures=[]
    def chat(self,system,messages,tools,max_tokens=4096,temperature=None):
        self.calls+=1;self.temperatures.append(temperature)
        if self.calls==1:return Reply(tool_calls=[ToolCall('list',self.names['list_graphs'],{})])
        if self.calls==2:return Reply(tool_calls=[ToolCall('search',self.names['search_entities'],dict(graph_id='librarian-v2',query='DEFAULT_CONTEXT_TOKENS'))])
        if self.calls==3:
            rows=[v for m in messages if m.get('role')=='tool' for v in objects(m.get('content',''))]
            target=next(v for v in rows if v.get('qualified_name','').endswith('loop.py.DEFAULT_CONTEXT_TOKENS') and 'entity_id' in v)
            return Reply(tool_calls=[ToolCall('open',self.names['get_entity_content'],dict(graph_id='librarian-v2',entity_id=target['entity_id']))])
        return Reply(text='Offline access smoke complete.')

def main():
    with tempfile.TemporaryDirectory(prefix='geo-quality-access-') as tmp:
        harness=h.Harness(Path('D:/Librarian_V2/tmp/geo-grapher-wave4-continuation-stores/catalog.sqlite'),Path(tmp),
                          'library','uvx',False,1048576,'lead','librarian-v2',OUT/'quality-dist/geo_grapher-0.1.1-py3-none-any.whl')
        try:
            provider=Offline(harness.tools['geo_code'])
            result=harness.run(provider,'Graph librarian-v2: inspect the development fallback constant.',server='geo_code')
            result.pop('tool_text')
            assert len(result['per_call'])==3 and all(c['success'] for c in result['per_call'])
            assert result['tool_errors']==0 and result['librarian_tools_used']==[]
            assert provider.temperatures==[0.2]*4
            assert any(c['coverage'] and c['coverage'][0]['start_line'] is not None for c in result['per_call'])
            result.update(provider_calls=4,paid_provider_calls=0,passed=True)
            with (OUT/'profile-access-smoke.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
            print(json.dumps(dict(passed=True,tool_calls=3,paid_provider_calls=0,temperature=0.2)))
        finally:harness.close()
if __name__=='__main__':main()
