# CloudDeploy Product API

Product API for Lab 10: Testing & Deployment (Cloud).

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

Open http://127.0.0.1:8000/docs

## Run tests

```powershell
pytest tests/ -v
```
