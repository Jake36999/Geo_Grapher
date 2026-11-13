"""Protocol boundaries, rather than live benchmark-answer fixtures."""
import importlib.util
from pathlib import Path
import sys
import pytest

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
import score_recovery_eval as scoring

def test_original_all_markers_and_new_equivalence_are_distinct():
    key=dict(markers=['DEFINITION','APPLICATION'],legacy_marker_required=True)
    assert not scoring.correct('DEFINITION',key)
    assert scoring.correct('APPLICATION and DEFINITION',key)
    assert scoring.correct('APPLICATION',dict(markers=key['markers']))

def test_incomplete_cycle_never_reads_keys(tmp_path,monkeypatch):
    registration=tmp_path/'final.registration.json'
    registration.write_text('{"stage":"final"}')
    (tmp_path/'final.cycle-state.json').write_text('{"status":"closed","complete":false}')
    seen=[];original=scoring.read
    def observe(path):
        seen.append(Path(path));return original(path)
    monkeypatch.setattr(scoring,'read',observe)
    monkeypatch.setattr(sys,'argv',['score',str(registration)])
    with pytest.raises(ValueError,match='No keys'):scoring.main()
    assert len(seen)==2
