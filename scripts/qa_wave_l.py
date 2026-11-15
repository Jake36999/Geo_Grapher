"""Free cross-repository Wave L checks against an installed wheel and a disposable library."""
import argparse
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--wheel-python', type=Path, required=True)
    args = parser.parse_args(); base = args.base.resolve()
    if not base.is_relative_to(Path('G:/Libraries/_qa').resolve()) or base.exists():
        raise SystemExit('Use a fresh fixture path under G:/Libraries/_qa; first results are retained')
    if shutil.disk_usage(base.parent).free - 200 * 1024**2 < 5 * 1024**3:
        raise SystemExit('Estimated fixture: 200 MiB; insufficient 5 GiB reserve')
    base.mkdir()
    from resource_librarian.init import init
    from resource_librarian.vault import Vault
    from resource_librarian.folder_review import FolderReview
    from resource_librarian.registry import Context
    from resource_librarian import projects
    import resource_librarian.tools.plan_dispatch as dispatch
    from resource_librarian.packet_checks import verify_citations
    from geographer.graph_catalog import GraphCatalog
    from geographer.graph_router import GraphRouter
    from geographer.agent_requests import call_code
    from geographer.provenance import mcp_entries
    import geographer

    init(base / 'Fixture Library', name='Wave L free qualification')
    vault = Vault(base / 'Fixture Library'); source = base / 'Attached Sources'
    for name in ['src/own.py', 'third_party/reference.py']:
        path = source / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('def example(value):\n    return value + 1\n', encoding='utf-8')
    (source / 'Frank.env').write_text('synthetic refused fixture', encoding='utf-8')
    command = [str(args.wheel_python.resolve()), '-I', '-m', 'geographer']
    (vault.librarian / 'geographer.json').write_text(json.dumps(dict(enabled=True,
        command=command, wheel_version='0.2.0')), encoding='utf-8')
    review = FolderReview(vault); cards = review.survey(source)['cards']; accepted = []
    for name, purpose, label in [('src','own-current','fixture-own'), ('third_party','third-party','fixture-third-party')]:
        card = next(c for c in cards if c['path'] == name)
        accepted.append(review.accept(card['id'], card['folder_fingerprint'], purpose=purpose, graph=label, person=True))
    (base / 'accepted-cards.json').write_text(json.dumps(accepted, indent=2), encoding='utf-8')
    catalog = GraphCatalog(vault.librarian / 'geographer/catalog.sqlite'); router = GraphRouter(catalog)
    graphs = {g['label']: g for g in catalog.graphs()}; own = graphs['fixture-own']['graph_id']; third = graphs['fixture-third-party']['graph_id']
    results = []; packet_calls = []; model_calls = []
    class NoModelMcp:
        def status(self): return {'fixture':dict(enabled=True, accepted=True, connected=True)}
        def tool_names(self, server): return ['mcp__fixture__list_graphs', 'mcp__fixture__compile_task_packet']
    original_external, original_model = dispatch._call_external, dispatch._run_task
    def external(ctx, server, name, arguments):
        if name == 'list_graphs': return router.summary()
        packet_calls.append(arguments)
        return router.compile_task_packet(**arguments)
    def no_model(*arguments):
        model_calls.append(True); raise AssertionError('QA_NO_MODEL')
    dispatch._call_external, dispatch._run_task = external, no_model
    try:
        try:
            dispatch.dispatch_plan(Context(tier='contribute', vault=vault, extras={'mcp':NoModelMcp()}),
                dict(plan_id='scope-fixture', server='fixture', tasks=[dict(task_id='external-leaf', tier=3,
                    graph_id=third, anchors=['entity:not-read'], instruction='Describe.', depends_on=[])]))
            raise AssertionError('tier-3 task admitted')
        except ValueError as error:
            assert str(error).startswith('PLAN_SCOPE') and 'external-leaf' in str(error)
            results.append(dict(point='L4(a)', passed=True, code='PLAN_SCOPE', packets=len(packet_calls), models=len(model_calls)))
    finally:
        dispatch._call_external, dispatch._run_task = original_external, original_model
    assert not packet_calls and not model_calls
    entries = mcp_entries(catalog, command)
    assert third not in entries['geo-own-packets']['args'] and third in entries['geo-references']['args']
    scoped = GraphRouter(catalog, allowed=[own], tools='lead', consumer_role='clerk'); scoped.close()
    try: GraphRouter(catalog, allowed=[own,third], consumer_role='clerk'); raise AssertionError('third-party Clerk connection admitted')
    except ValueError as error: assert 'THIRD_PARTY_SCOPE' in str(error)
    results.append(dict(point='L4(b)', passed=True, configurations=entries))
    found = call_code(router, 'search_entities', dict(graph_id=third, query='example', profile='tier2_forager'))
    assert all(h['provenance']=='third_party' and h['cite_as'].startswith('fixture-third-party/') for h in found['result']['data']['hits'])
    with router.lease(third) as service:
        eid = service.store.connection.execute("SELECT entity_id FROM entities WHERE snapshot_id=? AND kind='function'", (graphs['fixture-third-party']['snapshot_id'],)).fetchone()[0]
    packet = router.compile_task_packet(third, ['entity:' + eid], 'Describe.', profile='tier2_forager')
    federation = router.federated_search([own,third], 'example', mode='lexical', agent=True)
    assert packet['provenance']=='third_party' and next(r for r in federation['results'] if r['graph_id']==third)['provenance']=='third_party'
    answer = dict(inputs=[], outputs=[], calls=[], not_determinable=[], claims=[dict(text='Our current system uses this code.', cite=packet['anchors'][0]['cite_as'])])
    checked = verify_citations(answer, packet); assert checked['provenance_errors']
    results.append(dict(point='L4(c)', passed=True, hits=len(found['result']['data']['hits']),
                        packet_anchors=len(packet['anchors']), answer_flags=checked['provenance_errors']))
    for kind, evidence, expected in [('concept_equivalence',[{'owner_decision':True}],'THIRD_PARTY_BRIDGE'),
                                      ('reference',[{'automatic':True}],'OWNER_DECISION_REQUIRED')]:
        try: catalog.add_bridge(own,'root',third,'root',kind,'synthetic fixture',evidence); raise AssertionError('bridge admitted')
        except ValueError as error: assert expected in str(error)
    assert not catalog.propose_bridges(own,third,kind='concept_equivalence')
    bridge = catalog.add_bridge(own,'root',third,'root','reference','Synthetic explicit QA decision',[{'owner_decision':True}])
    results.append(dict(point='L4(d)', passed=True, approved_reference=bridge, automatic_equivalences=0))
    projects._save(vault, dict(enabled=True, roots=[dict(id='legacy', path=str(source), writes=True)]))
    try:
        projects.edit(vault, source, 'third_party/reference.py','replace','changed','def example')
        raise AssertionError('write admitted')
    except Exception as error:
        assert 'READ_ONLY' in str(error) or 'read-only' in str(error)
    results.append(dict(point='L4(e)', passed=True, source_access='read_only'))
    report = dict(passed=True, model_calls=0, spend=0, installed_geographer=geographer.__file__,
        graph_count=len(graphs), results=results, credential_refusals=review.overview()['credential_refusals'])
    router.close(); catalog.close()
    (base / 'results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
