# WorkFlow API

Backend for **WorkFlow**, a tool that helps university students coordinate on assignments and semester projects. Teams, projects, tasks, comments, invites, real-time chat and notifications, all behind a JWT-secured REST API.

**Live demo**

- Web app: https://workflow1223.netlify.app
- API: https://workflow-api-k6nk.onrender.com
- Interactive API docs: https://workflow-api-k6nk.onrender.com/docs

> The API runs on a free Render instance, so the first request after a quiet period can take 30+ seconds while it wakes up.

**Demo account:** `<testuser1@example.com>` / `<admin>`

## Features

- **Auth:** registration, JWT login, change password, email-based password reset, and sessions that are revoked when a password changes.
- **Teams:** whoever creates a team becomes its manager. Roles are per team (`manager` or `member`), not global.
- **Projects:** a project can belong to several teams. Only a manager of one of its teams can edit or delete it.
- **Tasks:** belong to a project, can be assigned to a user and/or a team, and assignment is validated against project-team membership.
- **Comments:** on tasks, editable by the author or a project-team manager.
- **Invites:** managers invite people by email with a one-time token. Existing users accept in the app, new users auto-join when they sign up with the invite link.
- **Chat:** team chat rooms and direct messages over WebSockets, with edit/delete, message history, and a per-connection rate limit.
- **Notifications:** a private activity feed with read/unread state.
- **Account deletion:** verified by an emailed code, which anonymizes the user's messages and comments.
- **Error handling:** global handlers turn database errors into clean 409/500 responses without leaking internals.

## Tech stack

| Area                 | Tools                                               |
| -------------------- | --------------------------------------------------- |
| Language / framework | Python 3.11+, FastAPI, Pydantic v2                  |
| Database             | PostgreSQL (Neon), SQLAlchemy 2, Alembic, psycopg 3 |
| Auth                 | JWT (PyJWT), bcrypt                                 |
| Real-time            | FastAPI WebSockets                                  |
| Email                | Resend (HTTPS API)                                  |
| Testing              | pytest, FastAPI TestClient                          |
| Hosting              | Render (API), Netlify (frontend), Neon (database)   |

## Architecture

```text
app/
├── api/
│   ├── deps.py          # auth + permission dependencies
│   └── routes/          # thin HTTP handlers (auth, users, teams, projects, tasks, comments, invites, messages, notifications, ws)
├── services/            # business logic and authorization rules
├── models/              # SQLAlchemy models
├── schemas/             # Pydantic request/response models
├── core/                # config, security, exception handlers, WebSocket manager
├── db/                  # engine and session
└── main.py
alembic/                 # migrations
tests/                   # pytest suite
```

Routes stay thin, services hold the rules, and models/schemas are kept separate.

## API overview

Full details live in the interactive docs at `/docs`. Everything except health, login, registration and password reset requires a bearer token.

| Area          | Endpoints                                                                                               |
| ------------- | ------------------------------------------------------------------------------------------------------- |
| Health        | `GET /health`                                                                                           |
| Auth          | `POST /auth/login`, `/auth/change-password`, `/auth/forgot-password`, `/auth/reset-password`            |
| Users         | `POST /users/`, `GET/PUT /users/me`, `GET /users/`, `GET /users/{id}`, account deletion request/confirm |
| Teams         | `POST/GET /teams/`, `GET/PUT/DELETE /teams/{id}`, join, add/remove/list members                         |
| Projects      | CRUD on `/projects/`, plus link/unlink/list teams                                                       |
| Tasks         | CRUD on `/tasks/` with filters                                                                          |
| Comments      | CRUD on `/comments/`                                                                                    |
| Invites       | `POST/GET /teams/{id}/invites`, `GET /invites/mine`, `POST /invites/{token}/accept`                     |
| Messages      | team history, conversations, direct history, edit and delete                                            |
| Notifications | list, mark one read, mark all read                                                                      |
| WebSocket     | `WS /ws?token=...`                                                                                      |

## Running locally

Requires Python 3.11+ and a PostgreSQL database (a free Neon project works).

```powershell
git clone https://github.com/ifraheemfarooqui/Workflow_api.git
cd Workflow_api
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create a `.env` file:

```env
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require
SECRET_KEY=change-me-to-a-long-random-string
FRONTEND_URL=http://localhost:3000
CORS_ORIGINS=["http://localhost:3000"]

# Optional locally, required in staging/production
RESEND_API_KEY=
SMTP_FROM_EMAIL=onboarding@resend.dev
```

Apply migrations and start the server:

```powershell
alembic upgrade head
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs.

## Configuration

| Variable            | Purpose                                                                                    |
| ------------------- | ------------------------------------------------------------------------------------------ |
| `DATABASE_URL`      | Database connection string (`postgresql+psycopg://...`)                                    |
| `TEST_DATABASE_URL` | A **separate, disposable** database used by the tests                                      |
| `SECRET_KEY`        | JWT signing key (32+ characters in staging/production)                                     |
| `ENVIRONMENT`       | `development`, `test`, `staging` or `production`. The last two turn on stricter validation |
| `FRONTEND_URL`      | Used to build links in emails. Must be HTTPS in staging/production                         |
| `CORS_ORIGINS`      | JSON list of allowed origins. Must include `FRONTEND_URL` in staging/production            |
| `RESEND_API_KEY`    | API key for sending email                                                                  |
| `SMTP_FROM_EMAIL`   | Sender address for emails (the name is a leftover from an earlier SMTP setup)              |

In staging/production the app refuses to start with an insecure or incomplete configuration (short secret, localhost origins, missing email settings).

## Testing

```powershell
pytest -q
```

The suite has 100+ tests covering auth, users, teams, projects, tasks, comments, invites, messages, notifications and config validation. Email sending is mocked, so no real mail is sent.

Tests create and **drop all tables** in the database from `TEST_DATABASE_URL`, so point it at a throwaway database, never your real one.

## Deployment

- **Database:** Neon (use the pooled connection string).
- **API:** Render web service.
  - Build: `pip install -r requirements.txt`
  - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  - Health check path: `/health`
  - Set the environment variables from the table above.
- **Frontend:** Netlify, with `VITE_API_URL` set to the API URL.
- **Migrations:** run `alembic upgrade head` locally against the production database before or after a deploy that changes the schema.

The engine uses `pool_pre_ping` so connections survive Neon suspending idle databases.

## Known limitations

- **Email is in test mode.** Resend only delivers to the account owner's address until a sending domain is verified, so invites and password reset emails won't reach arbitrary addresses on the live demo.
- **Cold starts.** The free Render instance sleeps after about 15 minutes idle.
- **Single worker.** The WebSocket connection manager is in memory, so it needs one uvicorn worker. Scaling out would need something like Redis pub/sub.
- **Invite expiry and revoking** are not implemented yet (the `revoked` status exists but is only set when an email fails to send).

## Roadmap

- React + TypeScript frontend polish
- Invite expiry and a revoke endpoint
- Domain-verified email sending
- Redis-backed WebSocket fan-out
