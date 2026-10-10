# Workflow Security and Privacy Audit

**Audit date:** 2026-10-09  
**Scope:** Backend object authorization, account deletion and retained data, configuration, and backup/recovery documentation.

## Authorization findings and changes

| Finding | Status | Change or remaining action |
| --- | --- | --- |
| Authenticated non-members could read a team's details and member roster. | Fixed | Team detail and roster reads now require membership; missing teams still return 404. |
| Authenticated non-members could read projects, project-team associations, and all project records through detail/list routes. | Fixed | Project detail and associations require membership, and project listing is scoped to the caller's teams. |
| A manager could add or remove a project-team association without managing the affected team. | Fixed | The caller must manage every team being added or removed. |
| Authenticated users could read comments across teams, and a former member could edit/delete their own comment after leaving. | Fixed | Comment list/detail are membership-scoped; comment owners and project managers must still be project-team members to edit/delete. |
| `GET /users/{id}` returned profile details without authentication or contact checks. | Fixed | It now requires authentication and permits only the caller or a shared-team contact. |
| Password change/reset and account deletion revoked HTTP tokens but did not close already-open WebSockets. | Fixed | Revocation flows close that user's active sockets; incoming WebSocket frames also revalidate the token. |
| Team discovery and joining are open to every authenticated user. | **Policy-dependent / unresolved** | `GET /teams/` exposes team names and `POST /teams/{id}/join` permits self-joining. This preserves the existing discover-and-join behavior. If teams are intended to be private, define a visibility/invitation policy and restrict joining accordingly. |

### Existing and added negative coverage

The backend tests cover non-member access to team details/rosters, project detail/list/team associations, comment reads and writes, invitation listing, direct messages, user profile lookups, project-team association changes, and active WebSocket closure following credential revocation. Existing tests also cover task membership, invite email matching, team-message membership, and message ownership.

## Account deletion and retained information

Deletion anonymizes the account row (`name`, `email`, and password hash), revokes tokens, removes team memberships and password/deletion tokens, clears task assignment and comment/message author references, and preserves shared comment/message contents.

This audit found invitations could retain a deleted user's email address or inviter ID. Deletion now removes invitations created by that account or addressed to its current email. Tests verify these invite rows are removed while shared comment/message text remains.

Free-form shared content is not automatically scrubbed: message and comment bodies, task titles/descriptions, project names/descriptions, and team names can contain personal information. Task/project records do not retain a creator reference that would allow safe, reliable selective cleanup. Review the application's retention policy and provide a user-facing way to redact personal information from shared text where required. Direct-message history remains stored, but contact/team checks can make a conversation unavailable after membership removal; the persistence and visibility policy should be decided explicitly.

## Production configuration

`app/core/config.py` uses Pydantic settings. `DATABASE_URL`, `TEST_DATABASE_URL`, and `SECRET_KEY` are required at process startup; many security-sensitive durations and the algorithm have defaults rather than production validation. SMTP settings are optional at startup and checked when recovery/deletion email is requested. Basic SMTP checks cover missing host/from address, incomplete username/password pairs, and mutually enabled TLS modes.

The repository's application currently hard-codes localhost CORS origins, while `FRONTEND_URL` defaults to a localhost URL. The local `.env` was checked only for presence/consistency flags; its values and secrets were not printed. No production environment or deployment secret store was available, so production values, HTTPS, origin alignment, key strength/rotation, and actual email delivery settings are **not verified**.

## Backup and recovery

No backup/restore procedure, backup command, or backup artifact was found in the checked backend documentation or files. No restore was attempted: without an identified backup and an approved isolated recovery target, a restore test would be speculative and could risk data. Production databases were not accessed or modified.

Before deployment, document an encrypted, access-controlled backup cadence and retention policy, then test restoration into a separate non-production database and record recovery time and data-loss objectives.

## Verification

- Backend: `pytest -q` — **83 passed**. Uses the configured test database; the test and application database URL identities were confirmed distinct without printing credentials.
- Frontend: `npm test` — **10 passed across 7 files**.
- Frontend: `npm run build` — **passed**.
- Local configuration presence checks passed without displaying values. This is not a production configuration verification.
- Backup restore: **not performed**; no backup procedure or artifact was available.
- Full authorization assurance: **not claimed**. Open team discovery/self-join remains policy-dependent, and external deployment/database controls were outside this local review.
