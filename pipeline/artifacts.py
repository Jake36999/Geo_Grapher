"""Local artifact helpers; no model calls or corpus mutations on import."""
import hashlib
import json
import os
import tempfile
from pathlib import Path


WORK_DIR=Path(__file__).resolve().parent/'work'


def digest_file(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,delete=False,suffix='.tmp') as stream:
        temporary=Path(stream.name)
        try:
            json.dump(data,stream,ensure_ascii=False,indent=2,allow_nan=False)
            stream.flush();os.fsync(stream.fileno())
        except BaseException:
            stream.close();temporary.unlink(missing_ok=True);raise
    try:temporary.replace(path)
    finally:temporary.unlink(missing_ok=True)


def authors_list(value):
    # Legacy artifacts sometimes stored a JSON array inside a JSON string.
    for _ in range(2):
        if not isinstance(value,str):break
        try:decoded=json.loads(value)
        except ValueError:break
        if decoded==value:break
        value=decoded
    if value is None:return []
    if isinstance(value,str):return [value.strip()] if value.strip() else []
    if not isinstance(value,list) or any(not isinstance(a,str) for a in value):raise ValueError('authors must contain names, not nested objects')
    return value
