import ast
import json
from pathlib import Path
import re
import pytest

def parser():
    path=Path(__file__).parents[1]/'scripts/build_heldout_v2.py'
    fn=next(n for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name=='decode_array')
    namespace={'json':json,'re':re}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(path),'exec'),namespace)
    return namespace['decode_array']

def test_repair_container_keeps_both_duplicate_pairs_and_exact_text():
    raw='{"id":"one","question":"Exact first text.","id":"two","question":"Exact second text."}'
    assert parser()(raw)==[dict(id='one',question='Exact first text.'),dict(id='two',question='Exact second text.')]
    assert parser()('[{"id":"one","accept":false}]')==[dict(id='one',accept=False)]
    with pytest.raises(ValueError):parser()('{"unexpected":"No invented question"}')
