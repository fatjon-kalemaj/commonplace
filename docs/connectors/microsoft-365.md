# Microsoft 365 connectors (stub): outlook, teams, sharepoint

Designed, not implemented. All three use Microsoft Graph.

## Auth

Delegated permissions with the device code flow, so no client secret is needed.

1. In Entra ID, register an application. Supported account types: this organization only.
2. Under Authentication, enable **Allow public client flows**.
3. Add the delegated permissions below and have an admin grant consent if your tenant requires it.
4. `export MS_CLIENT_ID=... MS_TENANT_ID=...` (or store them with `commonplace secrets set`).
5. The first run prints a device code; the refresh token is kept in the OS keychain.

## Permissions (delegated, read-only)

| Connector | Permissions |
|---|---|
| outlook | `Mail.Read`, `Calendars.Read` |
| teams | `Chat.Read`, `ChannelMessage.Read.All` (admin consent) |
| sharepoint | `Sites.Read.All`, `Files.Read.All` |

## Incremental fetch

Graph delta queries: `/me/mailFolders/inbox/messages/delta`, `/me/chats/getAllMessages` with a
`lastModifiedDateTime` filter, and `/drives/{id}/root/delta`. The delta link is the cursor.
