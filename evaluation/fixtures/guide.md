# Durable write workflow

The durable write path is app/helpers.py.retry_save, reached through
app/service.py.process. The helper retries once after OSError.

## Historical note — deliberately stale

An old design claimed app/ui.py.submit called app/storage.py.save directly.
This paragraph is a documentary assertion, not evidence of the current call.

## Scope

app/other.py.detached has no static path to app/storage.py.save in this fixture.
No runtime trace has been collected. Lack of observation cannot prove absence.
