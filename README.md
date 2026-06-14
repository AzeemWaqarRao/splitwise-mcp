# Splitwise MCP Server

A small [MCP](https://modelcontextprotocol.io) server (built with
[FastMCP](https://gofastmcp.com)) that wraps the
[Splitwise API](https://dev.splitwise.com) so Claude can read and manage your
**expenses** directly.

## Tools

| Tool | What it does |
|------|--------------|
| `list_expenses` | List expenses (filter by group, friend, date ranges; paginated) |
| `get_expense` | Get one expense's full details by id |
| `create_expense` | Add an expense — split equally or with custom per-user shares |
| `update_expense` | Edit an existing expense |
| `delete_expense` | Delete an expense |

## Credentials

Each user supplies **their own** Splitwise API key (and optional default group id).
The server reads them per request, in this order:

1. **HTTP request headers** (multi-user / hosted) — preferred:
   | Header | Required | Purpose |
   |--------|----------|---------|
   | `X-Splitwise-Api-Key` | yes | The caller's Splitwise API key (Bearer token) |
   | `X-Splitwise-Group-Id` | no | Default group id when a tool omits `group_id` |
2. **Environment variables** (single-user / local fallback) — `SPLITWISE_API_KEY`,
   `SPLITWISE_GROUP_ID`.

This means one hosted deployment can serve many people: each person plugs in their
own key via their client config — no shared key, no per-user redeploy.

Get an API key at [dev.splitwise.com](https://dev.splitwise.com) → **Your apps** →
create an app → copy the **API key**. The group id is in the URL when you open a
group on splitwise.com.

---

## Deploy to FastMCP Cloud (hosted, multi-user)

FastMCP Cloud runs the server remotely and gives you one HTTPS URL that many
people can use — **each with their own key**, passed as a header. You (the owner)
don't need to put any Splitwise secret in the dashboard.

1. **Push this folder to a GitHub repo** (see "Git setup" below).
2. Go to [fastmcp.cloud](https://fastmcp.cloud), sign in with GitHub, and
   **create a project** from your repo.
3. Set the **entrypoint** to:

   ```
   server.py:mcp
   ```

   (FastMCP Cloud installs dependencies from `pyproject.toml` automatically.)
4. **Authentication:** so other people can connect, set the project's access to
   **public / unauthenticated**. The real credential is each user's
   `X-Splitwise-Api-Key` header, so the server doesn't need its own login gate.
   (No `SPLITWISE_*` env vars needed in the dashboard for the multi-user case.)
5. Deploy. You'll get a URL like `https://your-project.fastmcp.app/mcp`. Share it.

### How each user adds the server to Claude

Every user runs this with **their own** key and group id:

**Claude Code (CLI):**

```bash
claude mcp add --transport http splitwise https://your-project.fastmcp.app/mcp \
  --header "X-Splitwise-Api-Key: THEIR_API_KEY" \
  --header "X-Splitwise-Group-Id: THEIR_GROUP_ID"
```

**Other clients (JSON form):**

```json
{
  "mcpServers": {
    "splitwise": {
      "url": "https://your-project.fastmcp.app/mcp",
      "headers": {
        "X-Splitwise-Api-Key": "THEIR_API_KEY",
        "X-Splitwise-Group-Id": "THEIR_GROUP_ID"
      }
    }
  }
}
```

> Note: header-based config works in clients that support custom MCP headers
> (e.g. Claude Code). The Claude Desktop "Add custom connector" UI currently
> only takes a URL (no custom headers), so Desktop users would need a client
> that supports headers — or you'd move to OAuth. For most setups, Claude Code
> is the way each user plugs in their key.

---

## Run locally (stdio, optional)

You can also run it on your own machine without the cloud. Here the secrets DO
go in the Claude config (since the process runs locally):

```bash
uv sync   # install deps
```

**Claude Code (CLI):**

```bash
claude mcp add splitwise \
  -e SPLITWISE_API_KEY=your_api_key_here \
  -e SPLITWISE_GROUP_ID=your_default_group_id \
  -- uv run --directory /Users/azeemwaqar/Desktop/home/work/splitwise_mcp server.py
```

**Claude Desktop** `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "splitwise": {
      "command": "uv",
      "args": ["run", "--directory", "/Users/azeemwaqar/Desktop/home/work/splitwise_mcp", "server.py"],
      "env": {
        "SPLITWISE_API_KEY": "your_api_key_here",
        "SPLITWISE_GROUP_ID": "your_default_group_id"
      }
    }
  }
}
```

Inspect tools interactively:

```bash
uv run fastmcp dev server.py
```

---

## Git setup (for FastMCP Cloud)

```bash
cd /Users/azeemwaqar/Desktop/home/work/splitwise_mcp
git init
git add .
git commit -m "Splitwise expense MCP server"
# create an empty repo on GitHub, then:
git remote add origin https://github.com/<you>/splitwise-mcp.git
git branch -M main
git push -u origin main
```

`.env` is git-ignored, so your key never gets committed.

## Notes on splitting

- **Equal split** (default): omit `users`; the cost splits evenly across the group.
- **Custom split**: pass `users`, e.g.
  `[{"user_id": 123, "paid_share": "25.00", "owed_share": "12.50"}, ...]`.
  `paid_share` values must sum to `cost`, and so must `owed_share`. You can
  identify a user by `user_id`, or by `email` / `first_name` / `last_name`.

Scope is intentionally limited to expenses — no friends/groups/categories
management tools (yet).
