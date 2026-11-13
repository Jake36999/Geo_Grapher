"""Planning-dollar bounds shared by the registered evaluation meter and tests."""
import json
import math


def approved_budget(value):
    funded=float(value['funded_budget_usd']);start=float(value['starting_committed_usd'])
    cap=float(value['workflow_cap_usd']);ceiling=float(value['spendable_ledger_ceiling_usd'])
    minimum=max(2.,float(value['minimum_reserve_usd']))
    if not all(math.isfinite(x) for x in (funded,start,cap,ceiling,minimum)) or cap<=0:
        raise ValueError('Invalid owner budget approval')
    if abs(ceiling-start-cap)>1e-8 or funded-ceiling<minimum-1e-8:
        raise ValueError('Spendable ceiling must preserve the owner reserve and workflow cap')
    return ceiling


def reserve_cost(body,rate,*,sent_bytes=0):
    for key in ('input_per_1m','output_per_1m'):
        if type(rate.get(key)) not in (int,float) or not math.isfinite(rate[key]) or rate[key]<=0:raise ValueError('Invalid registered rate card')
    raw=json.dumps(body,ensure_ascii=False,sort_keys=True).encode('utf-8')
    maximum=body.get('max_tokens',4096)
    if type(maximum) is not int or not 1<=maximum<=4096:raise ValueError('Registered output bound exceeded')
    return ((max(len(raw),sent_bytes)+1000)*rate['input_per_1m']+maximum*rate['output_per_1m'])/1e6


def settlement(usage,rate,reserve):
    if all(type(usage.get(k)) is int and usage[k]>=0 for k in ('prompt_tokens','completion_tokens')):
        charge=(usage['prompt_tokens']*rate['input_per_1m']+usage['completion_tokens']*rate['output_per_1m'])/1e6
        return charge,'api_usage_estimate'
    return reserve,'reserve'
