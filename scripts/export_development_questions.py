"""Export opened development prompts without keys for runtime collection."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from eval_retrieval_offline import read_development


def main():
    root=Path(__file__).resolve().parents[1]/'data/eval/code-research'
    rows,_=read_development(root/'development30.json')
    for name,selected in (('development30.questions.json',rows),('original5.questions.json',[r for r in rows if r['original_five']])):
        with (root/name).open('x',encoding='utf-8') as f:json.dump([{k:r[k] for k in ('id','graph','question')} for r in selected],f,indent=2)
    print(json.dumps(dict(development=30,original=5,answer_keys_exported=False)))

if __name__=='__main__':main()
