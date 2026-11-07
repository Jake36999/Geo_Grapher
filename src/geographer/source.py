"""Read immutable repository inputs without importing or running repository code."""
from __future__ import annotations

import hashlib
import io
import subprocess
import tarfile
import re
import os
from fnmatch import fnmatchcase
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .model import digest

EXCLUDED = {".git", ".venv", "venv", "__pycache__", "node_modules", ".cache", "graphifyy"}
SUPPORTED = {".py", ".md", ".txt", ".js", ".ts", ".tsx", ".jsx"}


def valid_path(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and not any(x in {"..", "."} for x in path.parts) and ":" not in name and "\\" not in name


@dataclass
class Repository:
    repo_id: str
    revision: str
    files: dict[str, bytes]
    source_roots: tuple[str, ...] = ("",)
    resolution_group: str | None = None
    include_globs: tuple[str, ...] = ("*",)
    exclude_globs: tuple[str, ...] = ()

    def __post_init__(self):
        if not self.repo_id or self.repo_id == "@workspace":
            raise ValueError("Repository ID must be nonempty and not @workspace")
        if self.resolution_group is not None and (not isinstance(self.resolution_group,str) or not self.resolution_group.strip()):
            raise ValueError('resolution_group must be a nonempty explicit name')
        for name in self.files:
            if not valid_path(name):
                raise ValueError(f"Unsafe repository-relative path: {name}")
        for root in self.source_roots:
            if root and not valid_path(root):
                raise ValueError("Unsafe source root")

    @property
    def content_digest(self) -> str:
        return digest([(p, hashlib.sha256(b).hexdigest()) for p, b in sorted(self.files.items())])

    @classmethod
    def from_git(cls, path: Path, repo_id: str, revision: str, source_roots=("",)) -> "Repository":
        if not re.fullmatch(r"[0-9a-fA-F]{40,64}", revision):
            raise ValueError("Specify a full immutable Git commit hash")
        actual = subprocess.run(["git", "-C", str(path), "rev-parse", "--verify", revision + "^{commit}"],
                                check=True, capture_output=True, text=True).stdout.strip()
        args = ["git", "-C", str(path), "archive", "--format=tar", actual]
        if all(source_roots):
            args.extend(["--", *source_roots])
        data = subprocess.run(args, check=True, capture_output=True).stdout
        files = {}
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            for member in archive:
                name = member.name
                p = PurePosixPath(name)
                if member.isfile() and valid_path(name) and not EXCLUDED.intersection(p.parts) and p.suffix in SUPPORTED:
                    if member.size > 4 * 1024 * 1024:
                        raise ValueError(f"Input file exceeds 4 MiB: {name}")
                    stream = archive.extractfile(member)
                    assert stream is not None
                    files[name] = stream.read()
        return cls(repo_id, actual, files, tuple(source_roots))

    @classmethod
    def from_directory(cls, path: Path, repo_id: str, source_roots=("",), *, resolution_group=None,
                       include_globs=("*",), exclude_globs=(), max_files=10000, max_total_bytes=128*1024*1024) -> "Repository":
        root = path.resolve()
        if not root.is_dir():raise ValueError(f"Repository directory not found: {root}")
        cls(repo_id,"working-tree",{},tuple(source_roots),resolution_group,tuple(include_globs),tuple(exclude_globs))
        files = {}
        total_bytes=0
        def candidates():
            for directory,dirs,names in os.walk(root,followlinks=False):
                rel_dir=Path(directory).relative_to(root).as_posix()
                rel_dir='' if rel_dir=='.' else rel_dir
                def allowed_dir(name):
                    child=Path(directory)/name;rel='/'.join(filter(None,(rel_dir,name)))
                    return name not in EXCLUDED and not child.is_symlink() and not (getattr(child.lstat(),'st_file_attributes',0)&0x400) and not any(fnmatchcase(rel+'/',g) or fnmatchcase(rel,g) for g in exclude_globs) and (not all(source_roots) or any(r==rel or r.startswith(rel+'/') or rel.startswith(r.rstrip('/')+'/') for r in source_roots))
                dirs[:]=sorted(name for name in dirs if allowed_dir(name))
                for name in sorted(names):yield Path(directory)/name
        for p in candidates():
            if not p.is_file() or p.is_symlink():
                continue
            rel = p.relative_to(root)
            if all(source_roots) and not any(rel.as_posix()==r or rel.as_posix().startswith(r.rstrip('/')+'/') for r in source_roots):
                continue
            if EXCLUDED.intersection(rel.parts) or p.suffix not in SUPPORTED:
                continue
            if not any(fnmatchcase(rel.as_posix(),g) for g in include_globs) or any(fnmatchcase(rel.as_posix(),g) for g in exclude_globs):continue
            if not p.resolve().is_relative_to(root):
                raise ValueError("Repository path escaped root")
            if p.stat().st_size > 4 * 1024 * 1024:
                raise ValueError(f"Input file exceeds 4 MiB: {rel}")
            total_bytes+=p.stat().st_size
            if len(files)>=max_files or total_bytes>max_total_bytes:raise ValueError('Repository input exceeds selected file/byte budget; narrow the ingestion profile')
            files[rel.as_posix()] = p.read_bytes()
        provisional = cls(repo_id, "working-tree", files, tuple(source_roots),resolution_group,tuple(include_globs),tuple(exclude_globs))
        provisional.revision = "working-tree:" + provisional.content_digest
        return provisional

    def modules(self, rel_path: str) -> list[str]:
        modules = []
        for root in self.source_roots:
            prefix = root.rstrip("/") + "/" if root else ""
            if not rel_path.startswith(prefix):
                continue
            name = rel_path[len(prefix):]
            if not name.endswith(".py"):
                continue
            parts = name[:-3].split("/")
            if parts[-1] == "__init__":
                parts.pop()
            # A source root that is itself a package retains its import name.
            if root and root + "/__init__.py" in self.files:
                parts.insert(0, PurePosixPath(root).name)
            if parts:
                modules.append(".".join(parts))
        return sorted(set(modules))
