"""Dependency-closed priority packing with whole-envelope admission checks."""
from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
import heapq
from collections import OrderedDict

from .model import canonical, digest

PACKER_VERSION='packer-v2-incremental'


class BudgetTooSmall(ValueError):
    def __init__(self,minimum):
        self.minimum=minimum
        super().__init__(f"Minimum successful payload needs {minimum} accounting units")


@dataclass
class Unit:
    id:str
    tier:int
    utility:float
    records:dict
    required:bool=False


def record_key(collection,record):
    if collection=='paths':return (record['source'],record['target'])
    keys={"nodes":"id","relationships":"id","witnesses":"id","evidence_handles":"id",
          "hits":"node_id","results":"node_id","matches":"node_id","findings":"id",
          "spheres":"node_id","curves":"relationship_id"}
    if collection in keys:return record[keys[collection]]
    return digest(record)


def combine(mandatory,units,*,copy_records=True):
    data=deepcopy(mandatory) if copy_records else dict(mandatory)
    indexes={k:{record_key(k,r):r for r in v} for k,v in data.items() if isinstance(v,list) and (not v or isinstance(v[0],dict))}
    for unit in units:
        for collection,records in unit.records.items():
            index=indexes.setdefault(collection,{})
            for record in records:index[record_key(collection,record)]=deepcopy(record) if copy_records else record
    for collection,index in indexes.items():
        values=list(index.values())
        if collection=="hits":values.sort(key=lambda r:(-r["score"],r["node_id"]))
        elif collection=="results":values.sort(key=lambda r:(r["hop_count"],r["node_id"]))
        elif collection=="chunks":values.sort(key=lambda r:(r["source"]["start_line"],r["sha256"]))
        elif collection.endswith('sibling_stubs'):values.sort(key=lambda r:(r['source']['start_line'],r['content_handle']))
        else:values.sort(key=lambda r:record_key(collection,r))
        if '.' in collection:
            parent,child=collection.split('.',1);data[parent]={**data[parent],child:values}
        else:data[collection]=values
    return data


def assert_closure(data):
    nodes={n["id"] for n in data["nodes"]}
    for record in data["relationships"]+data["witnesses"]:
        if record["source"] not in nodes or record["target"] not in nodes:
            raise AssertionError("Relationship without both endpoint definitions")
    spheres={s["node_id"] for s in data.get("spheres",[])}
    rels={r["id"]:r for r in data["relationships"]}
    for curve in data.get("curves",[]):
        r=rels.get(curve["relationship_id"])
        if r is None or r["source"] not in spheres or r["target"] not in spheres:
            raise AssertionError("Curve without endpoint spheres/relationship")
    for field in ("hits","matches","results"):
        if any(r["node_id"] not in nodes for r in data.get(field,[])):
            raise AssertionError("Query item without node definition")
    witnesses={w['id'] for w in data['witnesses']}
    for path in data.get('paths',[]):
        if any(step['relationship_id'] not in witnesses for step in path['steps']):raise AssertionError('Path without its original witnesses')


class GreedyPacker:
    def __init__(self,cursors):self.cursors=cursors;self.selections=OrderedDict()

    def pack(self,base,plan,counter,limit,delivered=(),page_size=200,transform=None,transform_key='canonical'):
        byid={u.id:u for u in plan.units}
        previous=set(delivered)
        mandatory_units=[u for u in plan.units if u.required and u.id not in previous]
        accepted=list(mandatory_units)
        mandatory_ids={u.id for u in mandatory_units}
        pending=[u for u in plan.units if u.id not in previous and u.id not in mandatory_ids]
        selection_key=(plan.snapshot_id,plan.query_digest,counter.name,counter.exact,limit,page_size,digest(sorted(previous)),transform_key)
        def finalise(units,*,commit=False):
            data=combine(plan.mandatory,units,copy_records=False)
            data['witnesses']=[dict(w) for w in data['witnesses']]
            for witness in data['witnesses']:
                evidence_plan=plan.evidence_plans.get(witness['id'])
                if evidence_plan:
                    if callable(evidence_plan):evidence_plan=evidence_plan()
                    returned=sorted(e['id'] for e in data['evidence_handles'] if e['relationship_id']==witness['id'])
                    witness['evidence_ids']=returned
                    evidence_units={u.id for u in evidence_plan.units}
                    returned_units={u.id for u in evidence_plan.units for e in u.records.get('evidence_handles',[]) if e['id'] in returned}
                    cumulative=(previous&evidence_units)|returned_units
                    witness['evidence_next_cursor']=(self.cursors.cursor(evidence_plan,cumulative,commit=commit)
                        if len(cumulative)<witness['evidence_total'] else None)
            current=previous|{u.id for u in units}
            remaining=len(plan.units)-len(current)
            totals=plan.totals
            if 'scene_completeness' in data:
                data['scene_completeness']=dict(data['scene_completeness'])
                data['scene_completeness']['omitted_spheres']+=max(0,totals.get('spheres',0)-len(data.get('spheres',[])))
                data['scene_completeness']['omitted_curves']+=max(0,totals.get('curves',0)-len(data.get('curves',[])))
            data["completeness"]=dict(truncated=remaining>0 or totals['nodes']>len(data['nodes']) or totals['relationships']>len(data['relationships'])+len(data['witnesses']),
                omitted_nodes=max(0,totals["nodes"]-len(data["nodes"])),
                omitted_relationships=max(0,totals["relationships"]-len(data["relationships"])-len(data["witnesses"])),
                omitted_items=remaining,next_cursor=self.cursors.cursor(plan,current,commit=commit) if remaining else None)
            if transform:data=transform(data)
            region={**base,"data":data}
            report=counter.report(region,limit)
            envelope={**region,"budget":report}
            return envelope,counter.cost(envelope)
        if selection_key in self.selections:
            cached=[byid[uid] for uid in self.selections[selection_key] if uid in byid]
            envelope,cost=finalise(cached,commit=True)
            if cost<=limit and envelope['budget']['used_tokens']<=limit:
                self.selections.move_to_end(selection_key);assert_closure(envelope['data']);return deepcopy(envelope)
        envelope,cost=finalise(accepted)
        if cost>limit or envelope["budget"]["used_tokens"]>limit:raise BudgetTooSmall(max(cost,envelope['budget']['used_tokens']))
        minimum_rejected=None
        # Marginal record costs are estimates. Only mandatory states, bounded
        # checkpoints and final commits tokenize the complete growing envelope.
        estimated=cost;last_checkpoint=len(accepted)
        for tier in sorted({u.tier for u in pending}):
            remaining={u.id:u for u in pending if u.tier==tier}
            dependencies={u.id:{(field,record_key(field,r)) for field,records in u.records.items() for r in records} for u in remaining.values()}
            reverse={}
            for uid,ds in dependencies.items():
                for dep in ds:reverse.setdefault(dep,set()).add(uid)
            def known_records(data):
                return {(field,record_key(field,r)) for field,records in data.items() if isinstance(records,list)
                        for r in records if isinstance(r,dict)}
            known=known_records(envelope['data']);versions={};failed={};heap=[]
            def enqueue(uid):
                if uid not in remaining:return
                unit=remaining[uid];signature=frozenset(dependencies[uid]&known)
                if failed.get(uid)==signature:return
                records={field:[r for r in values if (field,record_key(field,r)) not in known] for field,values in unit.records.items()}
                hint=max(1,counter.cost(records));versions[uid]=versions.get(uid,0)+1
                heapq.heappush(heap,(-unit.utility/hint,uid,versions[uid],hint))
            for uid in remaining:enqueue(uid)
            while heap and len(accepted)<page_size:
                _,uid,version,hint=heapq.heappop(heap)
                if uid not in remaining or versions[uid]!=version:continue
                candidate=remaining[uid]
                if len(accepted)-last_checkpoint>=16 or estimated+hint>limit-128 and len(accepted)!=last_checkpoint:
                    envelope,cost=finalise(accepted);estimated=cost;last_checkpoint=len(accepted)
                    failed.clear()
                    for other in sorted(remaining):
                        if other!=uid:enqueue(other)
                if estimated+hint>limit-128:
                    if not accepted:
                        proposed,proposed_cost=finalise([candidate])
                        if proposed_cost<=limit and proposed['budget']['used_tokens']<=limit:
                            estimated=proposed_cost-hint
                        else:
                            charge=max(proposed_cost,proposed['budget']['used_tokens'])
                            minimum_rejected=charge if minimum_rejected is None else min(minimum_rejected,charge)
                            failed[uid]=frozenset(dependencies[uid]&known);continue
                    else:
                        failed[uid]=frozenset(dependencies[uid]&known);continue
                accepted.append(candidate);remaining.pop(uid);estimated+=hint
                changed=dependencies[uid]-known;known|=changed
                affected=set().union(*(reverse.get(dep,set()) for dep in changed)) if changed else set()
                for other in sorted(affected):enqueue(other)
        if pending and not accepted and minimum_rejected is not None:
            raise BudgetTooSmall(minimum_rejected)
        # Re-finalisation is intentionally not assumed monotonic under BPE merges.
        while True:
            envelope,cost=finalise(accepted)
            if cost<=limit and envelope["budget"]["used_tokens"]<=limit:break
            optional=[u for u in accepted if not u.required]
            if not optional:raise BudgetTooSmall(cost)
            victim=max(optional,key=lambda u:(u.tier,-u.utility,u.id));accepted.remove(victim)
        # Bounded exact recovery at the budget boundary; estimates cannot mark
        # skipped records delivered. A fresh page can reconsider every omission.
        selected={u.id for u in accepted}
        recovery=sorted((u for u in pending if u.id not in selected),key=lambda u:(u.tier,-u.utility,u.id))[:8]
        for candidate in recovery:
            if len(accepted)>=page_size:break
            proposed,charge=finalise(accepted+[candidate])
            if charge<=limit and proposed['budget']['used_tokens']<=limit:accepted.append(candidate);envelope=proposed
        if pending and not accepted:
            minimum=None
            for candidate in pending:
                proposed,charge=finalise([candidate]);minimum=charge if minimum is None else min(minimum,charge)
                if charge<=limit and proposed['budget']['used_tokens']<=limit:accepted=[candidate];envelope=proposed;break
            if not accepted:raise BudgetTooSmall(minimum)
        assert_closure(envelope["data"])
        envelope,cost=finalise(accepted,commit=True)
        self.selections[selection_key]=[u.id for u in accepted]
        while len(self.selections)>512:self.selections.popitem(last=False)
        return deepcopy(envelope)
