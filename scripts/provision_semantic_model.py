"""Explicitly download public model assets; accepts no source/code input."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--destination',type=Path,required=True)
    p.add_argument('--receipt',type=Path,required=True)
    args=p.parse_args()
    if args.receipt.exists():raise SystemExit('Preserve first model-provisioning receipt')
    from huggingface_hub import HfApi,snapshot_download
    repo='minishlab/potion-base-8M'
    revision=HfApi(token=False).model_info(repo).sha
    snapshot_download(repo_id=repo,revision=revision,local_dir=args.destination,
        allow_patterns=['config.json','tokenizer.json','model.safetensors'],token=False)
    files={name:hashlib.sha256((args.destination/name).read_bytes()).hexdigest() for name in ('config.json','tokenizer.json','model.safetensors')}
    result=dict(repo=repo,revision=revision,files=files,source_inputs=0,hosted_embedding_calls=0)
    with args.receipt.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))

if __name__=='__main__':main()
