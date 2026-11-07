"""Small response identities for documentary queries; no writes or network calls."""
from contextvars import ContextVar
import hashlib
from pathlib import Path

API_VERSION = 'paper-tools-v4'
HERE = Path(__file__).resolve().parent
_FILES = ('mcp_doc_graph.py', 'corpus.py', 'query_context.py', 'maintain.py')


def source_build():
    digest = hashlib.sha256()
    for name in _FILES:
        digest.update(name.encode())
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()[:12]


BUILD_ID = source_build()
QUERY_CONTEXT = ContextVar('paper_query_context', default=None)
DATABASE_SCOPE = ContextVar('paper_database_scope', default=None)


class StaleCorpus(ValueError):
    pass


class ReadModelOutdated(ValueError):
    pass


def identity(revision):
    return dict(api_version=API_VERSION, server_build=BUILD_ID, corpus_revision=revision)
