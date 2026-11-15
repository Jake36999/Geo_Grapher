"""The owner ceiling excludes the reserve and bills uncertain attempts safely."""
import importlib.util
from pathlib import Path
import pytest


def module():
    path=Path(__file__).resolve().parents[1]/'scripts/eval_spending.py'
    spec=importlib.util.spec_from_file_location('spending',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m


def test_owner_ceiling_preserves_reserve_and_cannot_be_confused_with_funded_total():
    m=module();approval=dict(funded_budget_usd=16.25,starting_committed_usd=7.74739611,workflow_cap_usd=6.5,
        spendable_ledger_ceiling_usd=14.24739611,minimum_reserve_usd=2)
    assert m.approved_budget(approval)==pytest.approx(14.24739611)
    with pytest.raises(ValueError):m.approved_budget({**approval,'spendable_ledger_ceiling_usd':16.25})


def test_reservation_uses_utf8_bound_and_unknown_usage_retains_full_reserve():
    m=module();body=dict(messages=[dict(content='漢字'*100)],max_tokens=4096)
    rate=dict(input_per_1m=.3,output_per_1m=1.)
    reserve=m.reserve_cost(body,rate,sent_bytes=10000)
    assert reserve==pytest.approx((11000*.3+4096)/1e6)
    assert m.settlement({},rate,reserve)==(reserve,'reserve')
    charge,basis=m.settlement(dict(prompt_tokens=100,completion_tokens=20),rate,reserve)
    assert charge==pytest.approx(.00005) and basis=='api_usage_estimate'
