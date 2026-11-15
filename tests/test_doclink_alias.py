"""Documentary-link endpoints are decoded back to node ids under 1.1 canonical_map."""
from geographer.graph_composition import display_data


def test_display_data_decodes_documentary_link_endpoints(frame_for):
    frame_for(grouping={"mode": "atomic"}, identity_mode="canonical_map")
    result = frame_for.result
    assert result["data"]["documentary_links"], "fixture must yield documentary links"
    data = display_data(result)
    ids = {n["id"] for n in data["nodes"]}
    for link in data["documentary_links"]:
        assert link["fragment_rep"] in ids and link["entity_rep"] in ids
