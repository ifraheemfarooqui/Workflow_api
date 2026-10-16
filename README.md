# Workflow API

Workflow API is a FastAPI-based backend for managing collaborative teams, projects, tasks, comments, team invites, and team-scoped messaging. It also provides profile and password management and verified account deletion. The project follows a layered architecture with SQLAlchemy models, service functions, schema validation, and route handlers.

## Overview

This application models a lightweight team workflow system where:

- Users can register and authenticate with JWT-based access tokens.
- Teams are created and managed by team managers.
- Team members can join teams and collaborate on projects.
- Projects are attached to one or more teams.
- Tasks belong to projects and can be assigned to users in the same project team.
- Comments can be added to tasks and managed by the author or project manager.
- Team managers can create invites that users accept by email and token.
- Team members can send real-time team messages and direct messages to users who share a team.
- Members receive a private notification feed for team, project, task, membership, and comment activity; task notifications include project completion progress.
- Users can update profile details, change or reset passwords by email, and request verified account deletion.

## Tech Stack

- Python 3.11+
- FastAPI
- SQLAlchemy
- MySQL (local configuration) via SQLAlchemy and `DATABASE_URL`
- Alembic for database migrations
- Pydantic v2
- JWT via PyJWT
- pytest + FastAPI TestClient for testing
- bcrypt for password hashing

## Project Structure

```text
workflow_api/
├── alembic/
│   ├── versions/
│   ├── env.py
│   ├── README
│   └── script.py.mako
├── app/
│   ├── api/
│   │   ├── deps.py
│   │   └── routes/
│   │       ├── auth.py
│   │       ├── comments.py
│   │       ├── invites.py
│   │       ├── messages.py
│   │       ├── projects.py
│   │       ├── tasks.py
│   │       ├── teams.py
│   │       ├── users.py
│   │       └── ws.py
│   ├── core/
│   │   ├── config.py
│   │   ├── exceptions.py
│   │   └── security.py
│   ├── db/
│   │   ├── base.py
│   │   └── session.py
│   ├── models/
│   │   ├── account_deletion_code.py
│   │   ├── comment.py
│   │   ├── invite.py
│   │   ├── message.py
│   │   ├── password_reset_token.py
│   │   ├── project.py
│   │   ├── project_team.py
│   │   ├── task.py
│   │   ├── team.py
│   │   ├── team_membership.py
│   │   └── user.py
│   ├── schemas/
│   │   ├── comment.py
│   │   ├── invite.py
│   │   ├── message.py
│   │   ├── project.py
│   │   ├── task.py
│   │   ├── team.py
│   │   ├── token.py
│   │   └── user.py
│   ├── services/
│   │   ├── account_deletion_service.py
│   │   ├── comment_service.py
│   │   ├── invite_service.py
│   │   ├── message_service.py
│   │   ├── password_reset_service.py
│   │   ├── project_service.py
│   │   ├── task_service.py
│   │   ├── team_service.py
│   │   └── user_service.py
│   ├── __init__.py
│   └── main.py
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_comments.py
│   ├── test_invites.py
│   ├── test_messages.py
│   ├── test_projects.py
│   ├── test_tasks.py
│   ├── test_teams.py
│   └── test_users.py
├── alembic.ini
├── requirements.txt
└── README.md
```

Create a local `.env` file for configuration; it is ignored by Git and should never contain values committed to the repository.

## Application Entry Point

The app is initialized in [app/main.py](app/main.py). It creates the FastAPI application, registers all routers, and attaches global exception handlers.

```python
app = FastAPI()
app.include_router(users.router)
app.include_router(teams.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(comments.router)
app.include_router(auth.router)
app.include_router(invites.router)
app.include_router(messages.router)
app.include_router(ws.router)
```

The root health check route is:

- `GET /health`

Response:

```json
{
  "status": "healthy"
}
```

## Configuration

Application settings are defined in [app/core/config.py](app/core/config.py).

Environment variables (local-development example):

```env
DATABASE_URL=postgresql://username:password@host:port/workflow
TEST_DATABASE_URL=postgresql://username:password@host:port/workflow_test
SECRET_KEY=your-very-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
FRONTEND_URL=http://localhost:3000
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES=30
PASSWORD_RESET_REQUEST_COOLDOWN_SECONDS=60
ACCOUNT_DELETION_CODE_EXPIRE_MINUTES=10
ACCOUNT_DELETION_CODE_COOLDOWN_SECONDS=60
ACCOUNT_DELETION_CODE_MAX_ATTEMPTS=5
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-sender@gmail.com
SMTP_PASSWORD=your-google-app-password
SMTP_FROM_EMAIL=your-sender@gmail.com
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

The configuration loads from a `.env` file using Pydantic settings. The environment block above is a local-development example: `DATABASE_URL` and `SECRET_KEY` are required by the application, while `TEST_DATABASE_URL` is only needed for automated tests and must identify a separate disposable database. Never point the test database setting at staging or production. `ENVIRONMENT` accepts `development`, `test`, `staging`, or `production`.

For staging and production, set `ENVIRONMENT` explicitly, use an HTTPS `FRONTEND_URL`, and set `CORS_ORIGINS` to a JSON array of HTTPS origins including the frontend origin. Localhost origins, a short secret key, missing SMTP host/sender, incomplete SMTP credentials, and conflicting SMTP TLS settings fail application startup in those environments. Generate a unique `SECRET_KEY` in the deployment secret manager; do not put real values in source control or deployment documentation. Never print secrets during configuration checks.

Example non-secret staging origin settings:

```env
ENVIRONMENT=staging
FRONTEND_URL=https://workflow-staging.example.com
CORS_ORIGINS=["https://workflow-staging.example.com"]
```

SMTP settings are required to deliver password recovery and account-deletion emails. For Gmail, enable 2-Step Verification and create a Google App Password; use that app password (not the normal account password) for `SMTP_PASSWORD`. Keep sender credentials in the local `.env` file or deployment secret store, and do not commit or share them. For implicit TLS (commonly port 465), set `SMTP_USE_SSL=true` and `SMTP_USE_TLS=false`. Before running the API with the password and account-deletion features, apply database migrations with `alembic upgrade head`.

### Password management

- `POST /auth/change-password` verifies the signed-in user's current password, changes the hash, and revokes existing access tokens.
- `POST /auth/forgot-password` sends a single-use recovery link when the email belongs to an account. Its response does not reveal whether the email exists.
- `POST /auth/reset-password` validates the expiring, hashed token and changes the password.
- `POST /users/me/deletion/request` requires the current password and emails a short-lived confirmation code.
- `POST /users/me/deletion/confirm` validates the one-time code, removes the user's team memberships, anonymizes message and comment authorship, unassigns tasks, and revokes existing access tokens. Deletion is blocked until the user transfers manager access for any team they exclusively manage.
- Deletion removes invitations created by the account or addressed to its email. Shared free-form text (messages, comments, task/project descriptions, and names) is preserved and may still contain personal information.

#### Deletion retention risk and recommended policy

Account deletion anonymizes message/comment authorship and removes account-linked memberships, invitations, and assignments, but it does not inspect or rewrite shared message bodies, comments, task/project descriptions, or team/project names. Such text can contain the deleted person's name, contact details, or other personal information, and deleting the account does not guarantee that all personal data has been erased.

Recommended policy: preserve collaboration history by default, but clearly disclose that shared content remains; establish a documented retention schedule and legal-hold process; and provide an authorized, auditable workflow to redact content that contains personal or legally restricted information. Avoid blanket deletion of shared content because it can destroy useful team history and affect other users. This recommendation is documentation only; it does not change deletion behavior.

Password recovery requests for an existing account are rate-limited by a per-account cooldown. Tokens are stored only as SHA-256 hashes and expire after the configured period.
Deletion codes are stored only as keyed hashes, expire after the configured period, and are limited to a small number of attempts.

## API functionality

All HTTP routes below use the `/` prefix shown. **Public** routes do not require a bearer token; all other routes require a valid bearer token. Any additional team-membership or manager requirement is stated in the functionality column. FastAPI serves the OpenAPI schema at `/openapi.json` and interactive docs at `/docs`.

| Area | Routes | Functionality |
| --- | --- | --- |
| Health | `GET /health` (Public) | Reports API health. |
| Authentication | `POST /auth/login` (Public) | Exchanges email and password for a bearer token. |
| Authentication | `POST /auth/change-password` (Authenticated) | Verifies the current password, updates the password, and invalidates existing sessions. |
| Authentication | `POST /auth/forgot-password`, `POST /auth/reset-password` (Public) | Requests a non-enumerating email recovery link and consumes a one-time expiring reset token. |
| Users | `POST /users/`, `POST /users/bulk` (Public) | Creates one account or a batch of accounts. |
| Users | `GET /users/me`, `PUT /users/me` (Authenticated) | Reads or updates the signed-in user's name and email. |
| Users | `GET /users/` (Authenticated) | Lists only users sharing at least one team with the caller; `search` matches name or email and `skip`/`limit` paginate. |
| Users | `GET /users/{user_id}` (Authenticated) | Retrieves the caller's own profile or a teammate's profile; other users are forbidden. |
| Account deletion | `POST /users/me/deletion/request`, `POST /users/me/deletion/confirm` (Authenticated) | Sends and validates an email confirmation code; anonymizes retained message/comment authors, unassigns tasks, removes memberships and revokes sessions. Sole-manager deletion is rejected. |
| Teams | `POST /teams/`, `GET /teams/`, `GET /teams/{team_id}` | Creates a team (creator becomes manager), lists only the signed-in user's teams, or reads a team. |
| Teams | `PUT /teams/{team_id}`, `DELETE /teams/{team_id}` (Manager) | Updates or deletes a team. |
| Membership | `POST /teams/{team_id}/join`, `GET /teams/{team_id}/members` | Joins a team or lists its members. |
| Membership | `POST /teams/{team_id}/members/{user_id}`, `POST /teams/{team_id}/members`, `DELETE /teams/{team_id}/members/{user_id}` (Manager) | Adds one or multiple members, or removes a member. |
| Projects | `POST /projects/`, `GET /projects/`, `GET /projects/{project_id}` | Creates, lists, or reads projects. Project creation is restricted to a member of an associated team. |
| Projects | `PUT /projects/{project_id}`, `DELETE /projects/{project_id}` (Manager) | Updates or deletes a project. |
| Project teams | `POST /projects/{project_id}/teams`, `DELETE /projects/{project_id}/teams/{team_id}`, `GET /projects/{project_id}/teams` | Adds, removes, or lists teams associated with a project. |
| Tasks | `POST /tasks/`, `GET /tasks/`, `GET /tasks/{task_id}` (Authenticated team member) | Creates, filters/lists, or reads project tasks. Creation and assignment require project-team membership; a task may be assigned to a linked team and an individual. |
| Tasks | `PUT /tasks/{task_id}`, `DELETE /tasks/{task_id}` (Project-team member) | Updates or deletes a task. |
| Comments | `POST /comments/`, `GET /comments/`, `GET /comments/{comment_id}` | Adds or reads task comments. Comment creation checks project-team access. |
| Comments | `PUT /comments/{comment_id}`, `DELETE /comments/{comment_id}` | Allows the comment author or a project-team manager to update/delete a comment. |
| Messaging | `GET /teams/{team_id}/messages`, `GET /messages/conversations`, `GET /messages/direct/{user_id}` (Authenticated) | Reads team history (team member), latest direct conversations, or direct history. Direct-message participants must share a team. History supports `before_id` and `limit`. |
| Messaging | `PATCH /messages/{message_id}`, `DELETE /messages/{message_id}` | Edits or soft-deletes the caller's message; changes are broadcast to connected participants. |
| Messaging | `WS /ws?token=...` | Authenticated real-time send/receive for team and direct messages; the server limits each socket to 10 frames per 10 seconds. |
| Invites | `POST /teams/{team_id}/invites`, `GET /teams/{team_id}/invites` (Manager) | Emails or lists team invitations. Invitation delivery requires SMTP configuration. |
| Invites | `GET /invites/mine`, `POST /invites/{token}/accept` (Authenticated) | Lists invitations sent to the signed-in account and accepts one. |
| Notifications | `GET /notifications/`, `PATCH /notifications/{notification_id}/read`, `POST /notifications/read-all` (Authenticated) | Lists the caller's team activity, marks one notification read, or marks all as read. Task changes include project and linked-team completion counts. |

**Authorization note:** team and project mutation permissions are enforced by route dependencies and services. User listing and direct-message access are explicitly restricted to shared-team contacts. Consult the route modules and service modules for precise status codes and validation details.

## Verification

Run the backend suite from `workflow_api/`:

```powershell
.\venv\Scripts\pytest.exe
```

Tests use the database configured by `TEST_DATABASE_URL`; they cover authentication, profiles, password recovery, account deletion, comments, invites, messages, projects, tasks, and teams. SMTP delivery in automated tests is mocked. The tests do not send real mail or delete real accounts.

Apply pending schema migrations from `workflow_api/` with:

```powershell
.\venv\Scripts\alembic.exe upgrade head
```

Alembic obtains its database URL from `DATABASE_URL` via application settings; `alembic.ini` intentionally contains no fallback database URL. Before deployment, take and verify a database backup, check the current revision with `alembic current`, review pending revisions, and apply migrations as a controlled release step. Prefer backward-compatible expand/migrate/contract changes so the currently running application can tolerate the intermediate schema. Do not assume downgrades are safe; rollback may require deploying the previous application version and restoring a verified backup into a separate database, following the recovery runbook below.

### Database backup and restore runbook (MySQL)

Use a MySQL-compatible `mysqldump`/`mysql` client from a trusted operations host. The examples use Windows Command Prompt (`cmd.exe`) redirection. Keep the connection file and backup outside the repository, restrict file permissions, encrypt backups at rest and in transit, and use a dedicated least-privilege backup account. Do not place passwords in command-line arguments, shell history, logs, or this document. Replace example database and file names with approved values, and verify the target host and database identity before every operation.

1. Quiesce writes or use an engine/configuration that supports a consistent InnoDB snapshot. Record the deployed application version and `alembic current` revision.
2. Create a timestamped logical backup without `--databases` (so its contents can be restored to a different database):

   ```cmd
   mysqldump --defaults-extra-file="C:\secure\mysql-backup.cnf" --single-transaction --routines --triggers --events --hex-blob --default-character-set=utf8mb4 workflow_db > "D:\encrypted-backups\workflow-YYYYMMDD-HHMMSS.sql"
   ```

3. Check the command exit code and non-zero file size, then record a SHA-256 hash:

   ```cmd
   certutil -hashfile "D:\encrypted-backups\workflow-YYYYMMDD-HHMMSS.sql" SHA256
   ```

   Transfer/store the backup only in the approved encrypted backup location. Monitor backup completion and retention without logging credentials.
4. To recover, first provision a new, uniquely named isolated restore database on a verified non-production test server. Confirm its host and database name; do not overwrite, drop, or restore into an existing application database. Restore the logical dump:

   ```cmd
   mysql --defaults-extra-file="C:\secure\mysql-restore.cnf" --database=workflow_restore_test_YYYYMMDD < "D:\encrypted-backups\workflow-YYYYMMDD-HHMMSS.sql"
   ```

5. Verify table counts, the Alembic revision, representative relationships, and application startup against that isolated database. Record the restore duration and discrepancies. Keep the exercise separate from `DATABASE_URL`; never test recovery against production.

The MySQL command-line clients were unavailable in this development environment, so a backup/restore exercise has not been performed here. Obtain an approved staging recovery window and complete a restore drill before relying on this procedure.

### Staging deployment verification checklist

- [ ] Set `ENVIRONMENT=staging`, a strong unique `SECRET_KEY`, a staging-only `DATABASE_URL`, an HTTPS `FRONTEND_URL`, and matching HTTPS `CORS_ORIGINS` in the staging secret/configuration store.
- [ ] Configure the staging SMTP host, sender, and TLS mode; verify mail only with an authorized test inbox.
- [ ] Confirm the staging database identity and credentials without printing values; ensure `TEST_DATABASE_URL` is absent or points only to a separate disposable test database.
- [ ] Preserve the confirmed team policy: teams are discoverable and authenticated users may self-join; do not change this behavior as part of deployment configuration.
- [ ] Run backend tests, frontend tests, and the frontend production build from the release candidate.
- [ ] Take and verify a staging backup; check `alembic current`, inspect the migration diff, then run `alembic upgrade head` as a controlled step.
- [ ] Start the API and verify `/health`, CORS preflight from the configured frontend origin, authentication, and representative team/project/task/message flows.
- [ ] Exercise password recovery and account deletion only with a disposable staging account and authorized test inbox; verify account removal/anonymization and shared-content retention behavior.
- [ ] Review application and database logs for errors and confirm they do not contain SQL statements, bound parameters, secrets, or user-submitted text.
- [ ] Record the release, schema revision, backup location, test results, and rollback decision before promoting beyond staging.

See [SECURITY-AUDIT.md](SECURITY-AUDIT.md) for the authorization/privacy audit findings and previously verified results.

## Database and Persistence

The database connection is configured in [app/db/session.py](app/db/session.py).

- `engine = create_engine(settings.DATABASE_URL)`
- `SessionLocal` is the SQLAlchemy session factory.
- `get_db()` yields a database session for each request.

The base model class is in [app/db/base.py](app/db/base.py), and all ORM models inherit from it.

### Core Data Model

#### User

Defined in [app/models/user.py](app/models/user.py).

Fields:

- `id`
- `name`
- `email`
- `hashed_password`

Relationships:

- `team_memberships`
- `tasks`
- `comments`

#### Team

Defined in [app/models/team.py](app/models/team.py).

Fields:

- `id`
- `name`

Relationships:

- `team_memberships`
- `project_teams`

#### TeamMembership

Defined in [app/models/team_membership.py](app/models/team_membership.py).

Fields:

- `id`
- `user_id`
- `team_id`
- `role_in_team` (`member` or `manager`)

Unique constraint:

- one user can only belong to a team once

#### Project

Defined in [app/models/project.py](app/models/project.py).

Fields:

- `id`
- `name`
- `description`

Relationships:

- `project_teams`
- `tasks`

#### ProjectTeam

Defined in [app/models/project_team.py](app/models/project_team.py).

Fields:

- `id`
- `project_id`
- `team_id`

This bridges projects to multiple teams.

#### Task

Defined in [app/models/task.py](app/models/task.py).

Fields:

- `id`
- `title`
- `description`
- `status` (`todo`, `in_progress`, `done`)
- `priority` (`low`, `medium`, `high`)
- `project_id`
- `assigned_to`

Relationships:

- `project`
- `assignee`
- `comments`

#### Comment

Defined in [app/models/comment.py](app/models/comment.py).

Fields:

- `id`
- `content`
- `user_id`
- `task_id`

#### Invite

Defined in [app/models/invite.py](app/models/invite.py).

Fields:

- `id`
- `team_id`
- `invited_by`
- `email`
- `token`
- `status` (`pending`, `accepted`, `revoked`)
- `created_at`

## Authentication and Authorization

Authentication is handled by JWT tokens created in [app/core/security.py](app/core/security.py).

Core functions:

- `hash_password(password: str) -> str`
- `verify_password(plain_password: str, hashed_password: str) -> bool`
- `create_access_token(data: dict, expire_time: timedelta | None = None) -> str`
- `decode_access_token(token: str) -> dict`
- `generate_invite_token() -> str`

### Login flow

The login endpoint is available at:

- `POST /auth/login`

It accepts OAuth2 form data:

```text
username=<email>
password=<password>
```

Response:

```json
{
  "access_token": "...",
  "token_type": "bearer"
}
```

### Authorization dependencies

The main auth dependencies are in [app/api/deps.py](app/api/deps.py):

- `get_current_user` - verifies the JWT and loads the current user
- `require_team_manager` - ensures the active user is a manager of the given team
- `require_project_team_manager` - ensures the user is a manager on a project’s team
- `require_task_project_member` - ensures the user is a member of the task’s project team

## API Routes

### Authentication

#### `POST /auth/login`

Logs in with email and password and returns a JWT access token.

### Users

Routes are defined in [app/api/routes/users.py](app/api/routes/users.py).

- `POST /users/` - register a new user
- `GET /users/{user_id}` - fetch a user by ID
- `POST /users/bulk` - create several users in one request
- `GET /users/` - list users with pagination

Request example:

```json
{
  "name": "Alice",
  "email": "alice@example.com",
  "password": "secret123",
  "invite_token": "optional-token"
}
```

### Teams

Routes are defined in [app/api/routes/teams.py](app/api/routes/teams.py).

- `POST /teams/` - create a team
- `GET /teams/{team_id}` - fetch a team
- `GET /teams/` - list teams
- `PUT /teams/{team_id}` - update team (manager-only)
- `DELETE /teams/{team_id}` - delete team (manager-only)
- `POST /teams/{team_id}/members/{user_id}` - add a member
- `POST /teams/{team_id}/members` - bulk-add members
- `DELETE /teams/{team_id}/members/{user_id}` - remove a member
- `GET /teams/{team_id}/members` - list team members
- `POST /teams/{team_id}/join` - user joins a team

Team membership behavior:

- The creator of a team automatically becomes a `manager`.
- A user may join via the join endpoint or an accepted invite.
- Managers can email a team invitation link to an existing account or a new user. Existing users accept by signing in with the invited email; new users join during registration with the invitation link.

### Projects

Routes are defined in [app/api/routes/projects.py](app/api/routes/projects.py).

- `POST /projects/` - create a project under a specific team
- `GET /projects/{project_id}` - fetch one project
- `GET /projects/` - list projects
- `PUT /projects/{project_id}` - update project (project-team manager only)
- `DELETE /projects/{project_id}` - delete project (project-team manager only)
- `POST /projects/{project_id}/teams` - attach teams to a project
- `DELETE /projects/{project_id}/teams/{team_id}` - remove a team from a project
- `GET /projects/{project_id}/teams` - list teams associated with a project

Project creation rules:

- The creating user must already be a member of the selected team.
- Projects are linked to teams via the `project_teams` relation.

### Tasks

Routes are defined in [app/api/routes/tasks.py](app/api/routes/tasks.py).

- `POST /tasks/` - create a task
- `GET /tasks/` - list tasks with filters
- `GET /tasks/{task_id}` - fetch a task
- `PUT /tasks/{task_id}` - update a task
- `DELETE /tasks/{task_id}` - delete a task

Supported task filters:

- `project_id`
- `assigned_to`
- `status`
- `priority`
- `skip`
- `limit`

Valid task states:

- `todo`
- `in_progress`
- `done`

Valid task priorities:

- `low`
- `medium`
- `high`

Task assignment rules:

- The assignee must be a member of the same project team.
- A user can only view tasks tied to projects they belong to.

### Comments

Routes are defined in [app/api/routes/comments.py](app/api/routes/comments.py).

- `POST /comments/` - create a comment on a task
- `GET /comments/` - list comments with filters
- `GET /comments/{comment_id}` - fetch a comment
- `PUT /comments/{comment_id}` - update a comment
- `DELETE /comments/{comment_id}` - delete a comment

Rules:

- Only members of the task’s project team may comment.
- A user can edit/delete their own comment.
- A project manager may also edit/delete another user’s comment.

### Invites

Routes are defined in [app/api/routes/invites.py](app/api/routes/invites.py).

- `POST /teams/{team_id}/invites` - create a team invite
- `GET /teams/{team_id}/invites` - list pending invites for a team
- `POST /invites/{token}/accept` - accept an invite using a token

Invite rules:

- Only team managers can create invites.
- Invites must match the invited email address.
- Invite status moves from `pending` to `accepted` when accepted.
- Users can receive invite-based auto-membership during registration via `invite_token`.

## Service Layer

Business logic is kept in the service modules:

- [app/services/user_service.py](app/services/user_service.py)
- [app/services/team_service.py](app/services/team_service.py)
- [app/services/project_service.py](app/services/project_service.py)
- [app/services/task_service.py](app/services/task_service.py)
- [app/services/comment_service.py](app/services/comment_service.py)
- [app/services/invite_service.py](app/services/invite_service.py)

This separation keeps the route files thin and centralizes validation, permission checks, and database operations.

## Pydantic Schemas

Schemas are defined in [app/schemas](app/schemas). They validate request and response models for all major entities.

Notable schemas:

- `UserCreate`, `UserOut`
- `TeamCreate`, `TeamUpdate`, `TeamOut`
- `CreateProject`, `ProjectOut`
- `CreateTask`, `TaskUpdate`, `TaskOut`
- `CommentCreate`, `CommentUpdate`, `CommentOut`
- `InviteCreate`, `InviteOut`

## Error Handling

The application registers global error handlers in [app/main.py](app/main.py):

- `IntegrityError` -> database integrity handler
- `SQLAlchemyError` -> SQLAlchemy error handler
- `Exception` -> fallback unhandled error handler

Route-level validation also returns common HTTP results such as:

- `401 Unauthorized` for invalid or missing JWTs
- `403 Forbidden` for permission violations
- `404 Not Found` when resources or memberships do not exist
- `409 Conflict` for duplicate user emails

## Testing

The repository includes a pytest suite under [tests](tests).

### Run all tests

```bash
pytest
```

### Run a focused module

```bash
pytest tests/test_tasks.py
```

### Test setup

The test environment is configured in [tests/conftest.py](tests/conftest.py):

- Connects to the database configured by `TEST_DATABASE_URL`, not `DATABASE_URL`
- Creates a fresh database schema for each test
- Overrides the application database dependency with a test DB session
- Provides a reusable `client` fixture and `authenticated_client` fixture

After each test, the fixture closes its session and drops all tables from the
test database. Data created during a test is therefore temporary and does not
persist for the next test. **Set `TEST_DATABASE_URL` to a dedicated test
database**: because the fixture drops its tables, pointing it at a database
containing data you want to keep can delete that data.

Current test coverage includes:

- authentication and login
- team creation and team membership rules
- project creation and manager permissions
- task creation and assignment validation
- comment permissions and ownership rules
- invite creation and acceptance flow
- team and direct-message history, inbox, and WebSocket messaging

## Alembic Migrations

The project uses Alembic migrations in the [alembic](alembic) directory.

Typical migration commands:

```bash
alembic upgrade head
alembic revision --autogenerate -m "describe change"
```

This is useful when altering the database schema or adding new models.

## Local Development

1. Create a virtual environment:

```bash
python -m venv venv
```

2. Activate it:

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create a `.env` file with the required values.

5. Apply migrations:

```bash
alembic upgrade head
```

6. Start the API:

```bash
uvicorn app.main:app --reload
```

The app will be available at:

```text
http://127.0.0.1:8000
```

Swagger docs are automatically generated by FastAPI at:

```text
http://127.0.0.1:8000/docs
```

## Security Notes

- Passwords are never stored in plain text; they are hashed with bcrypt.
- JWTs are used for access control.
- The project enforces role-aware permissions for managers and team/project membership checks.
- Invite tokens are used to authorize team membership before registration or after signup.

## Summary

This backend provides a complete workflow platform for team-based collaboration. It includes user accounts, team membership, project association, task tracking, task comments, and email-based invite flows. The codebase is organized into clear model, schema, service, and route layers so it remains easy to extend as new project features are added.
