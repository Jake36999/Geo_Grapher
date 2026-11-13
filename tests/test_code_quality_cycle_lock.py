"""Paid dispatch is one-shot; the key stays closed throughout collection."""
import importlib.util
from pathlib import Path
import pytest

@pytest.fixture
def runner(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('quality_runner',Path(__file__).parents[1]/'scripts/run_code_quality_track.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'OUT',tmp_path)
    monkeypatch.setattr(module,'REGISTRATION',tmp_path/'registration.json')
    monkeypatch.setattr(module,'append',lambda text:None)
    monkeypatch.setattr(module,'frozen',lambda:{'candidate':'fixture'})
    module.create(module.REGISTRATION,{'candidate':'fixture'})
    return module

def test_closed_cycle_cannot_dispatch_again(runner,monkeypatch):
    runner.create(runner.OUT/'final-cycle-state.json',{'status':'closed'})
    monkeypatch.setattr(runner,'dispatch',lambda *a,**k:pytest.fail('No paid dispatch after closure'))
    with pytest.raises(FileExistsError):runner.cycle()

def test_ab_cannot_repeat(runner,monkeypatch):
    runner.create(runner.OUT/'ab-started.json',{})
    monkeypatch.setattr(runner,'dispatch',lambda *a,**k:pytest.fail('No repeated diagnostic calls'))
    with pytest.raises(FileExistsError):runner.ab()

def test_key_is_first_read_only_after_all_six_raw_runs(runner,monkeypatch):
    dispatched=[];original_read=runner.read
    def dispatch(label,*args,**kwargs):
        dispatched.append(label)
        total=25 if 'heldout' in label else 5
        rows=[dict(question_id=f'q{i}',answer='ANSWER',markers_found=['ANSWER'],per_call=[],tool_calls=1,
                   wrong_graph_calls=0,withheld_oversize=0) for i in range(total)]
        return rows,dict(cost_usd=0)
    def read(path):
        if path.name=='heldout.answers.sealed.json':
            assert len(dispatched)==6
            return [dict(id=f'q{i}',marker='ANSWER',entity_id='entity:fixture',source='m.py',span=[1,2]) for i in range(25)]
        return original_read(path)
    monkeypatch.setattr(runner,'dispatch',dispatch);monkeypatch.setattr(runner,'read',read)
    runner.cycle()
    assert runner.read(runner.OUT/'final-cycle-summary.json')['passed']
    assert runner.read(runner.OUT/'final-cycle-state.json')['status']=='closed'

def test_partial_cycle_closes_without_reading_the_key(runner,monkeypatch):
    calls=[]
    def dispatch(*args,**kwargs):calls.append(1);raise SystemExit('transport failure')
    original_read=runner.read
    def read(path):
        assert path.name!='heldout.answers.sealed.json'
        return original_read(path)
    monkeypatch.setattr(runner,'dispatch',dispatch);monkeypatch.setattr(runner,'read',read)
    with pytest.raises(SystemExit):runner.cycle()
    assert runner.read(runner.OUT/'final-cycle-state.json')==dict(status='closed',complete=False,no_repeat=True)
    with pytest.raises(FileExistsError):runner.cycle()
    assert len(calls)==1
