def test_frame_emits_documentary_link_between_doc_and_code(frame_for):
    data = frame_for(grouping={"mode": "kind", "kind": "file"})
    links = data["documentary_links"]
    assert any(l["role"] in {"documents", "discusses"} for l in links)
    ids = {n["id"] for n in data["nodes"]}
    assert all(l["fragment_rep"] in ids and l["entity_rep"] in ids for l in links)  # endpoint closure
    sphere_ids = {s["node_id"] for s in data["spheres"]}
    assert all(l["fragment_rep"] in sphere_ids and l["entity_rep"] in sphere_ids for l in links)
    assert all(l["link_id"].startswith("doclink:") and len(l["link_id"]) == len("doclink:") + 24 for l in links)
    assert all(l["degree"] in (1, 2, 3) and l["incidence_count"] >= 1 and len(l["control_points"]) >= 2 for l in links)
    assert [(-l["incidence_count"], l["link_id"]) for l in links] == sorted((-l["incidence_count"], l["link_id"]) for l in links)


def test_documentary_links_are_deterministic_and_budgeted(frame_for):
    a = frame_for(grouping={"mode": "atomic"}, curve_budget=1)
    b = frame_for(grouping={"mode": "atomic"}, curve_budget=1)
    assert a["documentary_links"] == b["documentary_links"] and len(a["documentary_links"]) <= 1


def test_documentary_links_pass_wire_validation(frame_for):
    frame_for(grouping={"mode": "kind", "kind": "file"})
    frame_for.svc.wire11.validate("viewport_frame", "response", frame_for.result)
