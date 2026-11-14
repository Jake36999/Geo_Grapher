"""Owner-operated qualification commands. Default is a read-only plan; no secrets printed."""
import argparse,json,urllib.request,urllib.parse,urllib.error
from pathlib import Path

MODELS={'research_helper':'google/gemma-4-26B-A4B-it','clerk':'Qwen/Qwen3.5-397B-A17B'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--role',choices=MODELS,required=True)
    p.add_argument('--level',choices=['L0','L1'],default='L1');p.add_argument('--run',action='store_true')
    p.add_argument('--confirm-spend',action='store_true');p.add_argument('--status',action='store_true');a=p.parse_args()
    if a.run and a.level=='L1' and not a.confirm_spend:raise SystemExit('L1 needs the owner’s explicit --confirm-spend')
    from resource_librarian import connection,process_identity
    from resource_librarian.vault import Vault
    from resource_librarian.role_routes import RoleRouteStore
    vault=Path('D:/Resource-Library/.librarian-app')
    binding=RoleRouteStore(Vault(vault)).resolve(a.role)
    if binding.model_id!=MODELS[a.role]:raise SystemExit('Selected route changed; owner approval required before choosing another model')
    record=connection.load(vault)
    if not record or not process_identity.is_alive(int(record.get('pid') or 0),record.get('process_start')):
        raise SystemExit('Start the Resource-Library Core first (see gate report); no qualification call sent')
    base=record['url'].rstrip('/');parsed=urllib.parse.urlparse(base)
    if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost','::1'):raise SystemExit('Core must be loopback HTTP')
    args=dict(host_id=binding.host_id,model=binding.model_id,role=a.role,level=a.level)
    path='/api/qualification/run' if a.run else '/api/qualification' if a.status else '/api/qualification/plan'
    body=json.dumps({**args,'confirm_spend':a.confirm_spend}).encode() if a.run else None
    url=base+path+('' if a.run else '?'+urllib.parse.urlencode(args))
    req=urllib.request.Request(url,data=body,headers={'X-Librarian-Token':record['token'],'Origin':base,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=300) as response:result=json.load(response)
    except urllib.error.HTTPError as exc:
        result=json.loads(exc.read());print(json.dumps(result,indent=2));raise SystemExit(1)
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
