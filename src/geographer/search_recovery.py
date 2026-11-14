"""Search-side episode accounting; MCP metadata keeps plain tool arguments small."""
from collections import OrderedDict
from contextvars import ContextVar
from copy import deepcopy
from .model import digest
from .search_fusion import observation,rank_queries,queries

META=ContextVar('geographer_recovery_metadata',default=None)


def state_for(router,connection,question):
    meta=META.get() or {}
    if not isinstance(meta,dict):raise ValueError('Recovery metadata must be an object')
    mode=meta.get('mode','auto');remaining=meta.get('remaining_steps',3)
    if mode not in {'auto','defer','off'} or type(remaining) is not int or not 0<=remaining<=3:
        raise ValueError('Recovery mode/remaining_steps invalid')
    original=meta.get('question',question)
    used=meta.get('used_patterns',[])
    if not isinstance(used,list) or len(used)>9 or any(not isinstance(p,str) or p not in {'FP'+str(n) for n in range(1,10)} for p in used):
        raise ValueError('Invalid recovery used_patterns')
    if not isinstance(original,str) or not original.strip() or len(original)>10000:raise ValueError('Recovery question must contain 1..10000 characters')
    episode=meta.get('episode_id')
    if episode is not None and (not isinstance(episode,str) or not 1<=len(episode)<=100):raise ValueError('Invalid recovery episode_id')
    cache=getattr(router,'search_recovery_episodes',None)
    if cache is None:cache=router.search_recovery_episodes=OrderedDict()
    key=(connection,episode) if episode else None
    if key is not None and key in cache:
        state=cache[key]
        if state['question_digest']!=digest(original):raise ValueError('Recovery episode question changed')
        cache.move_to_end(key)
    else:
        state=dict(question_digest=digest(original),steps=0,records={},cache={})
        if key is not None:
            if len(cache)>=1024:raise ValueError('Recovery episode capacity reached; restart this scoped server')
            cache[key]=state
    return state,original,mode,min(remaining,3-state['steps'])


def search(router,connection,index,texts,descriptions,*,semantic=None,kinds=()):
    state,question,mode,remaining=state_for(router,connection,texts[0])
    ranked=rank_queries(index,texts,semantic=semantic,kinds=kinds)
    lexical_obs=observation(ranked['lexical_hits'],question,descriptions,query=texts[0])
    disagree={h['node_id'] for h in ranked['lexical_hits'][:8]}!={h['node_id'] for h in ranked['semantic_hits'][:8]}
    fp2=semantic is not None and lexical_obs['low_confidence'] and disagree
    baseline=ranked['lexical_hits'] if fp2 else ranked['hits']
    obs=observation(baseline,question,descriptions,query=texts[0])
    triggers={}
    if texts[0].strip()!=question.strip() and obs['low_confidence']:triggers['FP1']=obs['confidence']
    if fp2:triggers['FP2']=dict(lexical_confidence=lexical_obs['confidence'],top8_disagree=True)
    used=(META.get() or {}).get('used_patterns',[])
    pending=[dict(pattern=p,trigger_value=v,action='verbatim_multiquery' if p=='FP1' else 'local_semantic_fusion')
        for p,v in triggers.items() if p not in state['records'] and p not in used]
    receipt=dict(recoveries=deepcopy(list(state['records'].values())),recovery_steps_consumed=0,recovery_pending=[])
    if mode=='defer':
        ranked['hits']=baseline;receipt['recovery_pending']=pending
    elif mode=='auto' and pending and remaining:
        key=digest(texts,list(kinds))
        if key not in state['cache']:
            corrected=queries(question,[text for text in texts if text!=question][:2]) if any(r['pattern']=='FP1' for r in pending) else texts
            repaired=rank_queries(index,corrected,semantic=semantic,kinds=kinds)
            state['cache'][key]=deepcopy(repaired)
        ranked=deepcopy(state['cache'][key]);state['steps']+=1
        step_id='search:'+str(state['steps'])
        after=observation(ranked['hits'],question,descriptions,query=question)
        for record in pending:
            resolved=not after['low_confidence'] and (record['pattern']!='FP2' or ranked['semantic_enabled'])
            state['records'][record['pattern']]={**record,'outcome':'resolved' if resolved else 'unresolved','step_id':step_id}
        receipt.update(recoveries=deepcopy(list(state['records'].values())),recovery_steps_consumed=1)
    elif mode=='auto' and not pending:
        cached=state['cache'].get(digest(texts,list(kinds)))
        if cached is not None:ranked=deepcopy(cached)
    receipt['recovery_steps_remaining']=max(0,remaining-receipt['recovery_steps_consumed'])
    return ranked,receipt


def id_advice(router,connection,gid,sid,exc,value):
    """A candidate menu is an observation, not an extra executable step."""
    state,_,mode,_=state_for(router,connection,value)
    if mode=='off' or not getattr(exc,'choices',None):return exc
    if 'FP6' in (META.get() or {}).get('used_patterns',[]) and 'FP6' not in state['records']:
        exc.choices=[];return exc
    if 'FP6' not in state['records']:
        state['records']['FP6']=dict(pattern='FP6',trigger_value={'error_code':'INVALID_GRAPH_REQUEST','candidate_count':len(exc.choices)},
            action='scoped_candidates',outcome='unresolved',step_id='observation:FP6',extra_steps=0)
        state['id_candidates']=(gid,sid,{row['entity_id'] for row in exc.choices})
        state['id_menu']=deepcopy(exc.choices)
    scope=state.get('id_candidates')
    if scope and scope[:2]==(gid,sid):exc.choices=deepcopy(state['id_menu'])
    else:exc.choices=[]
    exc.recoveries=deepcopy(list(state['records'].values()))
    return exc


def id_success(router,connection,gid,sid,eid):
    meta=META.get() or {};episode=meta.get('episode_id')
    state=getattr(router,'search_recovery_episodes',{}).get((connection,episode)) if episode else None
    if not state or 'FP6' not in state['records']:return {}
    scope=state.get('id_candidates')
    if scope and scope[:2]==(gid,sid) and eid in scope[2]:state['records']['FP6']['outcome']='resolved'
    return dict(recoveries=deepcopy(list(state['records'].values())))
