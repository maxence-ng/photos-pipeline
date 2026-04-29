---
id: SPEC-018
title: "SaaS Multi-User & Authentication"
status: todo
phase: intermediate
epic: saas
priority: high
effort: L
depends_on: ["SPEC-016"]
---

## User Story
As a SaaS operator, I want each user to have their own account with isolated jobs and files so that multiple photographers can use the same deployment without seeing each other's work.

## Acceptance Criteria
- [ ] `POST /api/v1/auth/register` — create account with email + password
- [ ] `POST /api/v1/auth/login` — returns a signed JWT access token (expires in 24 h) and a refresh token
- [ ] `POST /api/v1/auth/refresh` — issue a new access token using refresh token
- [ ] `POST /api/v1/auth/logout` — invalidate refresh token
- [ ] All job endpoints enforce authentication; a user can only see/modify their own jobs
- [ ] Passwords hashed with `bcrypt` (via `passlib`)
- [ ] JWT secret read from environment variable `JWT_SECRET` (never hardcoded)
- [ ] User data stored in SQLite (development) or PostgreSQL (production); use `SQLAlchemy` ORM
- [ ] Admin can list all users via `GET /api/v1/admin/users` (role: `admin`)
- [ ] Unit tests: register, login, access protected endpoint, access other user's job → 403

## Technical Notes
- Use `python-jose` for JWT; `passlib[bcrypt]` for password hashing
- Refresh tokens stored hashed in DB with expiry (30 days)
- User isolation: each user has a `user_id`; all job records and file paths are prefixed/scoped by `user_id`
- Storage directory structure: `<storage_root>/<user_id>/<job_id>/`

## Implementation Hints
```python
from passlib.context import CryptContext
from jose import jwt

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(user_id: str, expires_delta: timedelta) -> str:
    payload = {"sub": user_id, "exp": datetime.utcnow() + expires_delta}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
```
