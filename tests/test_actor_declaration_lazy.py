"""Module summaries must not traverse every function body to read a docstring."""
import ast
import pytest
from geographer.actor import ActorEncoder
from geographer.pipeline import Repository,ingest
from geographer.service import QueryService
from geographer.store import SnapshotStore

def test_file_doc_does_not_walk_bodies_and_legacy_function_still_works(monkeypatch):
    store=SnapshotStore()
    try:
        sid=ingest(store,[Repository('r','fixed',{'example.py':b'"""Module overview."""\ndef calculate(value):\n    """Return the increment."""\n    return value + 1\n'})],stage=3)['snapshot_id']
        service=QueryService(store,secret=b'x'*32);service.active_snapshot=sid
        ctx=service._context(sid);encoder=ActorEncoder(service,ctx,None)
        file=next(e for e in ctx['g'].entities.values() if e.kind=='file')
        fn=next(e for e in ctx['g'].entities.values() if e.kind=='function')
        ctx['g'].analyses.pop('declaration:'+file.entity_id,None)
        calls=[];original=ast.walk
        def walk(tree):calls.append(True);return original(tree)
        monkeypatch.setattr(ast,'walk',walk)
        assert encoder.declaration(file.entity_id)['docstring']=='Module overview.'
        assert calls==[]
        # Simulate an immutable legacy snapshot lacking persisted declarations.
        ctx['g'].analyses.pop('declaration:'+fn.entity_id,None)
        assert encoder.declaration(fn.entity_id)['signature']=='def calculate(value)'
        assert encoder.declaration(fn.entity_id)['docstring']=='Return the increment.'
        assert len(calls)==0
    finally:store.close()


@pytest.mark.parametrize('suite',[
    'if True:\n    {definition}\n',
    'try:\n    pass\nexcept Exception:\n    {definition}\n',
    'try:\n    pass\nfinally:\n    {definition}\n',
    'match value:\n    case _:\n        {nested}\n',
    'class Owner:\n    {definition}\n',
])
def test_legacy_definitions_inside_statement_suites_keep_their_descriptors(suite):
    definition='def nested(value):\n        """Nested documentation."""\n        return value'
    text=suite.format(definition=definition,nested=definition.replace('\n','\n    '))
    store=SnapshotStore()
    try:
        sid=ingest(store,[Repository('r','fixed',{'nested.py':text.encode()})],stage=3)['snapshot_id']
        service=QueryService(store,secret=b'x'*32);service.active_snapshot=sid;ctx=service._context(sid)
        encoder=ActorEncoder(service,ctx,None)
        entity=next(e for e in ctx['g'].entities.values() if e.qualified_name.endswith('.nested'))
        ctx['g'].analyses.pop('declaration:'+entity.entity_id,None)
        actual=encoder.declaration(entity.entity_id)
        assert actual['signature']=='def nested(value)' and actual['docstring']=='Nested documentation.'
    finally:store.close()
