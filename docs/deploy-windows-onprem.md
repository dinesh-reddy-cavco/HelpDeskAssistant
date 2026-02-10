# Windows VM (On-Prem) Deployment Guide

This guide deploys this app to an on-prem Windows VM:
- Frontend: static files in `frontend/`
- Backend: FastAPI app in `backend/`
- Backend exposed internally on `127.0.0.1:8000`
- IIS serves frontend and reverse-proxies `/api/*` to backend

## 1) Prerequisites

1. Windows Server VM with local admin access.
2. DNS entry for your app (example: `helpdesk.company.local`) pointing to VM.
3. Inbound firewall rules on VM/network:
   - `80` (HTTP) and `443` (HTTPS) from allowed client networks
   - `3389` (RDP) only from admin/jump networks
4. Outbound `443` from VM to Azure services used by app:
   - Azure AI Foundry endpoint
   - Azure AI Search endpoint

## 2) Install required software

Run PowerShell as Administrator:

```powershell
# Python 3.11
winget install -e --id Python.Python.3.11

# IIS role/services
Install-WindowsFeature Web-Server,Web-Static-Content,Web-Default-Doc,Web-Http-Errors,Web-Http-Redirect,Web-Http-Logging,Web-Request-Monitor,Web-Filtering,Web-Stat-Compression,Web-Mgmt-Console
```

Install IIS extensions:
1. URL Rewrite
2. Application Request Routing (ARR)

Enable ARR proxy:
1. Open IIS Manager.
2. Click server node.
3. Open `Application Request Routing Cache`.
4. Click `Server Proxy Settings...`.
5. Check `Enable proxy`.

## 3) Deploy application files

Copy repo to VM, for example:

`C:\apps\HelpDeskAssistant`

Expected structure:

```text
C:\apps\HelpDeskAssistant\
  backend\
  frontend\
  requirements.txt
  .env
```

## 4) Configure environment variables

Create/update:

`C:\apps\HelpDeskAssistant\.env`

Use production values for:
- `AZURE_FOUNDRY_ENDPOINT`
- `AZURE_FOUNDRY_API_KEY`
- `AZURE_FOUNDRY_DEPLOYMENT_NAME`
- `AZURE_SEARCH_ENDPOINT`
- `AZURE_SEARCH_KEY`
- `AZURE_SEARCH_INDEX_NAME`

Keep `.env` out of source control and rotate any exposed secrets.

## 5) Prepare backend runtime

```powershell
cd C:\apps\HelpDeskAssistant
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Validate backend:

```powershell
cd C:\apps\HelpDeskAssistant\backend
C:\apps\HelpDeskAssistant\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Test on VM:
- `http://127.0.0.1:8000/api/health`

Stop process after validation.

## 6) Run backend as Windows service

Install NSSM (recommended), then run:

```powershell
nssm install HelpDeskBackend "C:\apps\HelpDeskAssistant\.venv\Scripts\python.exe" "-m uvicorn app.main:app --host 127.0.0.1 --port 8000"
nssm set HelpDeskBackend AppDirectory "C:\apps\HelpDeskAssistant\backend"
nssm set HelpDeskBackend Start SERVICE_AUTO_START
nssm start HelpDeskBackend
```

Verify:

```powershell
Get-Service HelpDeskBackend
```

## 7) Configure IIS website

This repo includes `frontend/web.config` with reverse proxy for `/api/*`:
- `/api/...` -> `http://127.0.0.1:8000/api/...`

Create site:
1. IIS Manager -> `Sites` -> `Add Website`
2. Site name: `HelpDeskFrontend`
3. Physical path: `C:\apps\HelpDeskAssistant\frontend`
4. Binding: `http`, port `80`, host name your internal DNS name
5. Start website

Frontend uses same-origin API in deployed mode, so browser calls:
- `https://helpdesk.company.local/api/...`

## 8) Configure TLS certificate

Use your internal PKI or approved certificate source.

1. Import cert into Local Computer certificate store.
2. IIS site -> `Bindings` -> add `https` on `443`.
3. Select certificate.
4. Optionally add HTTP -> HTTPS redirect.

## 9) Validation checklist

1. `https://<your-hostname>/` loads frontend.
2. `https://<your-hostname>/api/health` returns healthy response.
3. Chat call to `/api/chat` succeeds from browser.
4. `Get-Service HelpDeskBackend` is `Running`.
5. Windows Event Viewer/IIS logs show no startup errors.

## 10) Update procedure

1. Stop backend service:

```powershell
nssm stop HelpDeskBackend
```

2. Replace app files under `C:\apps\HelpDeskAssistant`.
3. Reinstall dependencies if changed:

```powershell
cd C:\apps\HelpDeskAssistant
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

4. Start backend service:

```powershell
nssm start HelpDeskBackend
```

5. Restart IIS site if needed:

```powershell
iisreset
```

## Ops notes

- Backend reads `.env` from repo root (`C:\apps\HelpDeskAssistant\.env`).
- Default DB is SQLite (`chatbot.db`) in backend working directory; back it up regularly.
- If this becomes multi-user/critical, move from SQLite to managed SQL.
