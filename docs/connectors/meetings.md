# Meeting transcript connectors

## meeting_exports (working)

Reads exported files from a folder, offline:

| App | Export | How it is read |
|---|---|---|
| Fireflies | JSON transcript export | `sentences[].speaker_name/text`, `participants`, `summary.action_items` |
| Granola | Markdown note export | frontmatter `title`, `date`, `attendees`, or an `Attendees:` line |
| Wispr Flow | Plain text notes | first line is the title, the rest is the body |

A date at the start of a filename (`2026-09-22-...`) is used when the file has no date of its own.

```toml
[connectors.meeting_exports]
path = "~/Documents/Meeting exports"
```

## fireflies (stub)

The Fireflies GraphQL API (`https://api.fireflies.ai/graphql`) with an API key from
Integrations -> Fireflies API. Set `FIREFLIES_API_KEY`. The connector will only send
`query` operations (`transcripts(fromDate: ...)`, `transcript(id: ...)`); `ReadOnlyHTTP`
will reject any request body containing `mutation`.

## granola (stub)

Use `meeting_exports` with Granola's Markdown export until a stable public API is available.
