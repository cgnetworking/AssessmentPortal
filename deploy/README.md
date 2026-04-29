# Production Deployment

Target platform: Ubuntu 24.04 or newer.

## Setup Script

The preferred path is the setup coordinator, which calls task-specific scripts from `deploy/scripts/lib/`:

```bash
sudo deploy/scripts/setup_ubuntu.sh --domain assessment.example.com
```

The script installs OS prerequisites, copies the app to `/opt/assessmentportal`, builds the React frontend, creates the Python environment, installs pinned PowerShell module dependencies, installs systemd units, and installs the Nginx site config.

It does not start services while `/etc/assessmentportal/assessmentportal.env` still contains placeholder values.

## Packages

Install OS packages:

```bash
sudo apt update
sudo apt install -y nginx python3.12 python3.12-venv python3-pip postgresql-client powershell
```

Install Node.js from your approved source, then build the frontend:

```bash
cd /opt/assessmentportal/frontend
npm ci
npm run build
```

## Application User

```bash
sudo useradd --system --home /opt/assessmentportal --shell /usr/sbin/nologin assessmentportal
sudo mkdir -p /etc/assessmentportal /var/lib/assessmentportal/assessment-runs
sudo chown -R assessmentportal:assessmentportal /var/lib/assessmentportal
```

## Python Environment

```bash
cd /opt/assessmentportal
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd backend
python manage.py migrate
python manage.py collectstatic --noinput
```

## Environment

Copy and edit the environment template:

```bash
sudo cp /opt/assessmentportal/deploy/env/assessmentportal.env.example /etc/assessmentportal/assessmentportal.env
sudo chmod 640 /etc/assessmentportal/assessmentportal.env
sudo chown root:assessmentportal /etc/assessmentportal/assessmentportal.env
```

The Microsoft Entra app registration redirect URI must be:

```text
https://<host>/auth/complete/azuread-tenant-oauth2/
```

## Gunicorn and Worker

```bash
sudo cp /opt/assessmentportal/deploy/systemd/assessmentportal-gunicorn.service /etc/systemd/system/
sudo cp /opt/assessmentportal/deploy/systemd/assessmentportal-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now assessmentportal-gunicorn assessmentportal-worker
```

## Nginx

Edit `deploy/nginx/assessmentportal.conf` and replace `assessment.example.com` and certificate paths.

```bash
sudo cp /opt/assessmentportal/deploy/nginx/assessmentportal.conf /etc/nginx/sites-available/assessmentportal.conf
sudo ln -s /etc/nginx/sites-available/assessmentportal.conf /etc/nginx/sites-enabled/assessmentportal.conf
sudo nginx -t
sudo systemctl reload nginx
```

Nginx serves the React build and proxies `/api/`, `/auth/`, and `/admin/` to Gunicorn over a Unix socket.

## Version Pinning

Application Python dependencies are exact-pinned and SHA256 hash-pinned in `requirements.txt`. The lock is generated for Ubuntu 24.04 x86_64 with CPython 3.12 wheels, and includes transitive dependencies because pip hash mode requires the full dependency graph to be pinned.

Frontend direct dependencies are exact-pinned in `frontend/package.json`; the setup script uses `npm ci` when a lockfile is present and falls back to `npm install` otherwise.

ZeroTrustAssessment PowerShell module dependencies use `RequiredVersion` in the module manifest. The setup script also pins its bootstrap tooling defaults with `pip==25.3`, `wheel==0.45.1`, and `powershell=7.5.6-1.deb`.
