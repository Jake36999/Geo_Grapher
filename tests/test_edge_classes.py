import pytest
from geographer.edge_classes import classify_relationship, classify_documentary

@pytest.mark.parametrize("args,expected", [
    (("static", "calls", "exact"), ("call_or_data", "exact")),
    (("static", "calls", "candidate"), ("call_or_data", "candidate")),
    (("static", "imports", "exact"), ("hierarchy", "exact")),
    (("static", "inherits", "unresolved"), ("hierarchy", "candidate")),
    (("runtime", "calls", "observed"), ("call_or_data", "observed")),
    (("expected", "calls", "declared"), ("call_or_data", "expected_only")),
])
def test_classify_relationship(args, expected):
    assert classify_relationship(*args) == expected

def test_classify_documentary_roles():
    assert [classify_documentary(r) for r in ("rationale_for", "documents", "discusses", "cites")] == \
           ["doc_rationale", "doc_describes", "doc_describes", "doc_cites"]

def test_frame_curves_carry_classes(frame_for):
    curves = frame_for(grouping={"mode": "atomic"})["curves"]
    assert curves and all(c["relationship_family"] in {"call_or_data", "hierarchy"} and c["runtime_status"] for c in curves)

def test_frame_validates_and_doc_links_classified(frame_for):
    data = frame_for(grouping={"mode": "atomic"})
    assert frame_for.svc.wire11.validate('viewport_frame', 'response', frame_for.result)
    for link in data.get("documentary_links", []):
        assert link["relationship_family"].startswith("doc_") and link["runtime_status"] == "exact"
