# Postgres connector (stub)

Designed, not implemented. Turns rows from a query you write into records, for
example a CRM's `accounts` table becoming Company notes.

## Setup

1. Create a database role with `SELECT` on the tables you need and nothing else:

   ```sql
   CREATE ROLE commonplace_reader LOGIN PASSWORD '...';
   GRANT USAGE ON SCHEMA crm TO commonplace_reader;
   GRANT SELECT ON crm.accounts, crm.contacts TO commonplace_reader;
   ```

2. `export POSTGRES_DSN=postgresql://commonplace_reader@host/db` (password from `~/.pgpass` or the keychain).
3. Configure one query per record type:

   ```toml
   [connectors.postgres]
   enabled = true
   query = "SELECT id, name, owner, updated_at, notes FROM crm.accounts WHERE updated_at > %(since)s"
   kind_hint = "company"
   title_column = "name"
   body_column = "notes"
   ```

The connector will open every connection with `default_transaction_read_only = on`
and run queries inside `BEGIN READ ONLY`, so a misconfigured role still cannot write.
