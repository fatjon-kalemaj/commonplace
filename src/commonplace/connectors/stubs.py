"""Connectors that are designed but not yet implemented. Each one documents
its auth setup and the read-only scopes it will request."""

from __future__ import annotations

from .base import StubConnector


class GmailConnector(StubConnector):
    name = "gmail"
    description = "Gmail threads (scope: gmail.readonly)"
    secrets = ("GOOGLE_OAUTH_CLIENT_FILE",)
    auth_doc = "docs/connectors/google-workspace.md"


class GoogleDriveConnector(StubConnector):
    name = "google_drive"
    description = "Google Docs and Drive files (scope: drive.readonly)"
    secrets = ("GOOGLE_OAUTH_CLIENT_FILE",)
    auth_doc = "docs/connectors/google-workspace.md"


class GoogleCalendarConnector(StubConnector):
    name = "google_calendar"
    description = "Calendar events (scope: calendar.readonly)"
    secrets = ("GOOGLE_OAUTH_CLIENT_FILE",)
    auth_doc = "docs/connectors/google-workspace.md"


class OutlookConnector(StubConnector):
    name = "outlook"
    description = "Outlook mail and calendar via Microsoft Graph (Mail.Read, Calendars.Read)"
    secrets = ("MS_CLIENT_ID", "MS_TENANT_ID")
    auth_doc = "docs/connectors/microsoft-365.md"


class TeamsConnector(StubConnector):
    name = "teams"
    description = "Teams chats and channel messages via Graph (Chat.Read, ChannelMessage.Read.All)"
    secrets = ("MS_CLIENT_ID", "MS_TENANT_ID")
    auth_doc = "docs/connectors/microsoft-365.md"


class SharePointConnector(StubConnector):
    name = "sharepoint"
    description = "SharePoint and OneDrive documents via Graph (Sites.Read.All, Files.Read.All)"
    secrets = ("MS_CLIENT_ID", "MS_TENANT_ID")
    auth_doc = "docs/connectors/microsoft-365.md"


class FirefliesConnector(StubConnector):
    name = "fireflies"
    description = "Fireflies.ai transcripts via the GraphQL API (queries only)"
    secrets = ("FIREFLIES_API_KEY",)
    auth_doc = "docs/connectors/meetings.md"


class GranolaConnector(StubConnector):
    name = "granola"
    description = "Granola notes via API (use meeting_exports for exported notes today)"
    secrets = ("GRANOLA_API_KEY",)
    auth_doc = "docs/connectors/meetings.md"


class PostgresConnector(StubConnector):
    name = "postgres"
    description = "Rows from a Postgres query, one record per row (read-only transaction)"
    secrets = ("POSTGRES_DSN",)
    auth_doc = "docs/connectors/postgres.md"
