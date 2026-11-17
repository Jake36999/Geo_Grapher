"""Filename-only refusal policy; never inspect contents to make this decision.

Kept in step with the Librarian's `resource_librarian/credentials.py` (2026-11-17: Geo-Grapher
lacked its secret-store names and suffixes, so the two disagreed about the same folder).
"""
from pathlib import PurePosixPath


# Secret stores by name. Exact names, so a code file such as `credentials.py` or a paper about
# secret sharing is never refused.
SECRET_SUFFIXES = ('.secret', '-secret', '_secret', '.secrets')
SECRET_NAMES = frozenset({'secrets', 'secrets.json', 'secrets.yaml', 'secrets.yml', 'secrets.toml',
                          'credentials', 'credentials.json', '.netrc', '.pgpass', '.htpasswd'})


def credential_path(path) -> bool:
    for raw in PurePosixPath(str(path).replace('\\', '/')).parts:
        name = raw.casefold()
        if (name == 'certs' or name == '.env' or name.endswith('.env')
                or name.startswith(('.env.', 'id_'))
                or name.endswith(('.key', '.pem', '.p12', '.pfx'))
                or name.endswith(SECRET_SUFFIXES) or name in SECRET_NAMES):
            return True
    return False


def refuse_credentials(path):
    if credential_path(path):
        raise ValueError(f'CREDENTIAL_REFUSED: {path}')
