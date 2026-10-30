# Google Workspace connectors (stub): gmail, google_drive, google_calendar

Designed, not implemented. The plan, so the stubs can be filled in:

## Auth

OAuth 2.0 for an installed app, with the user's own Google Cloud project.

1. In Google Cloud console, create a project and enable the Gmail, Drive and Calendar APIs.
2. Configure the OAuth consent screen as **Internal** (Workspace) or **Testing** with yourself as a test user.
3. Create an OAuth client of type **Desktop app** and download the client JSON.
4. Point commonplace at it: `export GOOGLE_OAUTH_CLIENT_FILE=~/.config/commonplace/google-client.json`
5. On first run the connector opens a browser for consent and stores the refresh
   token in the OS keychain (service `commonplace`, key `GOOGLE_REFRESH_TOKEN`), never on disk.

## Scopes (read-only only)

| Connector | Scope |
|---|---|
| gmail | `https://www.googleapis.com/auth/gmail.readonly` |
| google_drive | `https://www.googleapis.com/auth/drive.readonly` |
| google_calendar | `https://www.googleapis.com/auth/calendar.readonly` |

## Incremental fetch

- Gmail: `users.history.list` from the stored `historyId`; first run uses a `q` filter such as `newer_than:30d label:clients`.
- Drive: `changes.list` with a stored page token; export Google Docs as `text/markdown`.
- Calendar: `events.list` with a `syncToken`. Events become meeting records and are merged with transcripts by title and start time.
