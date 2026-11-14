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


def test_sealed_key_change_is_rejected_before_scoring(tmp_path):
    import hashlib
    path=tmp_path/'answers.json';path.write_text('sealed')
    seal=dict(files={'answers.json':hashlib.sha256(path.read_bytes()).hexdigest()})
    scoring.validate_seal(seal,tmp_path)
    path.write_text('changed')
    with pytest.raises(ValueError,match='Sealed'):scoring.validate_seal(seal,tmp_path)
