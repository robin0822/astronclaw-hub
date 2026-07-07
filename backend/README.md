# AstronClaw Backend

FastAPI backend for AstronClaw enterprise management APIs.

## Local MySQL initialization

Default database URL:

```powershell
$env:DATABASE_URL="mysql+pymysql://astronclaw:astronclaw@127.0.0.1:3306/astronclaw?charset=utf8mb4"
```

If the database already exists and the user has DDL privileges:

```powershell
python -m pip install -r requirements.txt
python scripts/init_db.py
```

If the database does not exist, provide an admin URL that can create schemas:

```powershell
$env:MYSQL_ADMIN_URL="mysql+pymysql://root:your_password@127.0.0.1:3306/?charset=utf8mb4"
python scripts/init_db.py
```

Seeded admin account:

```text
username: admin
password: Admin@123456
```

## Run API server

```powershell
$env:DATABASE_URL="mysql+pymysql://astronclaw:astronclaw@127.0.0.1:3306/astronclaw?charset=utf8mb4"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

OpenAPI:

```text
http://127.0.0.1:8000/docs
```

Frontend API guide:

```text
FRONTEND_API.md
```

Base API path:

```text
/api/v1/astron-claw
```

## Test

```powershell
python -m pytest tests -q
```

The test suite uses SQLite isolation for API tests and the production code defaults to MySQL.
