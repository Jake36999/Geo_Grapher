"""Persistent cursor signing key shared by local queries and network transports."""
from pathlib import Path
import secrets


def persisted_secret(database: Path):
    path = database.with_suffix(database.suffix + '.cursor-secret')
    if not path.exists():
        try:
            with path.open('xb') as stream:
                stream.write(secrets.token_bytes(32))
        except FileExistsError:
            pass
    secret = path.read_bytes()
    if len(secret) != 32:
        raise ValueError('Invalid cursor-secret file')
    return secret
