"""Indexed class/member traversal and conservative open-world C3 dispatch."""
from __future__ import annotations
import ast
from collections import defaultdict
from .cfg import UNBOUND

class StaticDispatch:
    def build_class_index(self):
        self.members=defaultdict(lambda:defaultdict(list))
        self.class_scopes={unit.owners[scope]:(unit,scope) for unit in self.units for scope in unit.scopes.scopes if isinstance(scope.node,ast.ClassDef)}
        for eid,e in self.graph.entities.items():
            if e.parent_id:self.members[e.parent_id][e.qualified_name.rsplit('.',1)[-1].split('#')[0]].append(eid)
        self.definition_states={}
        for unit in self.units:
            for scope,cfg in unit.cfgs.items():
                self.definition_states.update(cfg.definition_states())
        self.class_bases={};self.class_base_facts=[];self.mros={}
        for eid,node in self.definition_nodes.items():
            if not isinstance(node,ast.ClassDef):continue
            unit=self.entity_units[eid];scope=unit.scopes.by_node[node]
            bid=self.binding_ids.get((id(node),node.name))
            state=self.definition_states.get(bid,{})
            bases=[];supported=not node.keywords and not node.decorator_list
            for base in node.bases:
                resolved=self.resolve_access(unit,scope,base,state)
                unique=sorted({(t,'candidate' if s=='exact' and self.graph.entities[t].kind!='class' else s) for t,s in resolved})
                facts=unique or [(self.external(unit,scope,ast.unparse(base),base),'unresolved')]
                self.class_base_facts.append((unit,eid,base,facts))
                if len(unique)!=1 or unique[0][1]!='exact' or self.graph.entities[unique[0][0]].kind!='class':supported=False
                else:bases.append(unique[0][0])
            self.class_bases[eid]=bases if supported else None
        def linearize(eid,active=()):
            if eid in self.mros:return self.mros[eid]
            if eid in active or len(active)>128:return None
            bases=self.class_bases.get(eid)
            if bases is None:return None
            seqs=[]
            for base in bases:
                mro=linearize(base,(*active,eid))
                if mro is None:return None
                seqs.append(list(mro))
            seqs.append(list(bases));result=[eid]
            while any(seqs):
                seqs=[s for s in seqs if s]
                head=next((s[0] for s in seqs if all(s[0] not in t[1:] for t in seqs)),None)
                if head is None:return None
                result.append(head)
                for s in seqs:
                    if s[0]==head:s.pop(0)
            self.mros[eid]=result;return result
        for eid in self.class_bases:linearize(eid)
        self.subclasses=defaultdict(set)
        for eid,mro in self.mros.items():
            for base in mro:self.subclasses[base].add(eid)
        for eid in self.class_bases:
            self.graph.analyses['mro:'+eid]=dict(algorithm_version='c3-static-v1',scope={'entity_id':eid},
                result={'mro':self.mros.get(eid),'status':'supported' if eid in self.mros else 'unsupported_or_inconsistent',
                        'dispatch_world':'open','runtime_dispatch_exact':False})

    def resolve_access(self,unit,scope,expression,state):
        parts=[]
        while isinstance(expression,ast.Attribute):parts.insert(0,expression.attr);expression=expression.value
        if not isinstance(expression,ast.Name):return []
        bids=self.lookup(unit,scope,expression.id,state);results=[]
        uncertain=len(bids)!=1 or UNBOUND in bids or expression.id in unit.attribute_mutations or scope.reflective
        for bid in sorted(bids):
            if bid==UNBOUND:continue
            b=self.bindings[bid]
            if parts and b.kind=='module':found=self.resolve_member(b.module,parts,{bid})
            elif parts and b.kind=='member':found=self.resolve_member(b.module,[b.member,*parts],{bid})
            elif parts:found=[x for target,_ in self.resolve_binding(bid) for x in self.target_members(target,parts,{bid})]
            else:found=self.resolve_binding(bid)
            results.extend((target,'candidate' if uncertain else status) for target,status in found)
        return results

    def target_members(self,target,parts,seen):
        if not parts:return [(target,'candidate')]
        guard=('target',target,tuple(parts))
        if guard in seen:return []
        seen=seen|{guard}
        entity=self.graph.entities[target]
        if entity.kind in {'file','directory'}:
            modules=self.module_names_for_entity.get(target,[])
            return [x for mod in modules for x in self.resolve_member(mod,parts,seen)]
        result=[]
        owners=self.mros.get(target,[target]) if hasattr(self,'mros') else [target]
        for owner in owners:
            hits=self.members.get(owner,{}).get(parts[0],[]) if hasattr(self,'members') else []
            if owner in getattr(self,'class_scopes',{}):
                unit,scope=self.class_scopes[owner]
                if parts[0] in unit.bindings[scope]:
                    bids=unit.final.get(scope,{}).get(parts[0],())
                    hits=[self.bindings[b].target for b in bids if b!=UNBOUND and self.bindings[b].kind=='definition']
                    # A concrete class assignment/deletion masks inherited slots;
                    # do not skip an unknown/noncallable slot to find a base method.
                    if not hits:return []
            if hits:
                for eid in hits:
                    result.extend([(eid,'candidate')] if len(parts)==1 else self.target_members(eid,parts[1:],seen))
                break
        return result

    def receiver_targets(self,unit,scope,expression,parts):
        if not parts or not isinstance(expression,ast.Name):return []
        node=scope.node
        if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) or not scope.parent or not isinstance(scope.parent.node,ast.ClassDef):return []
        args=[*node.args.posonlyargs,*node.args.args]
        if not args or args[0].arg!=expression.id or unit.bindings[scope].get(expression.id):return []
        decorators={ast.unparse(d) for d in node.decorator_list}
        if 'staticmethod' in decorators:return []
        # Receiver binding follows the first parameter, not the spelling self/cls.
        # Python permits arbitrary receivers and runtime overriding: candidates only.
        owner=unit.owners[scope.parent];result=[]
        for cls in sorted(self.subclasses.get(owner,{owner})):
            result.extend(self.target_members(cls,parts,set()))
        return sorted(set(result))
