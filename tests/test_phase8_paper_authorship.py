from test_paper_pipeline import paper_db
from pipeline import mcp_doc_graph as service


def test_paper_actor_projects_source_authorship_at_its_shared_boundary(paper_db):
    out = service._TOOLS['get_document']('doc:1')
    assert out['authorship'] == 'third_party'
    assert isinstance(out['provenance'], dict)
    assert out['provenance']['sources']
    assert out['authorship_scope'] == 'original_source'
