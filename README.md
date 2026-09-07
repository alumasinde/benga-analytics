# BengaAnalytics

Production-oriented dynamic Business Intelligence platform built with Flask, MongoDB, Pandas and vanilla JavaScript.

## Run

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

## Architecture

- `users`: authentication, tenant, tier and billing lifecycle.
- `datasets`: compact metadata/catalog documents.
- `records`: flexible row documents containing normalized data.
- `usage`: counters and quota enforcement.
- `saved_queries`: reusable analytical configurations.

## CI

GitHub Actions runs the test suite on Python 3.11 and 3.12 for pushes and pull requests targeting `main`. Tests use `mongomock`, so CI does not require a live MongoDB server.
