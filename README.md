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

## Configuration

The server reads two environment variables:

| Variable | Required | Purpose |
|----------|----------|---------|
| `SPLITWISE_API_KEY` | yes | Bearer token for the Splitwise API |
| `SPLITWISE_GROUP_ID` | no | Default group id used when a tool call omits `group_id` |

Get the API key at [dev.splitwise.com](https://dev.splitwise.com) → **Your apps** →
create an app → copy the **API key**. The group id is in the URL when you open a
group on splitwise.com.

---

## Deploy to FastMCP Cloud (hosted)

FastMCP Cloud runs the server remotely and gives you an HTTPS URL. **Secrets are
NOT put in the Claude config** — they live in the FastMCP Cloud dashboard as
environment variables. The Claude config only points at the URL.

1. **Push this folder to a GitHub repo** (see "Git setup" below).
2. Go to [fastmcp.cloud](https://fastmcp.cloud), sign in with GitHub, and
   **create a project** from your repo.
3. Set the **entrypoint** to:

   ```
   server.py:mcp
   ```

   (FastMCP Cloud installs dependencies from `pyproject.toml` automatically.)
4. In the project's **Environment Variables / Secrets**, add:

   ```
   SPLITWISE_API_KEY  = your_api_key_here
   SPLITWISE_GROUP_ID = your_default_group_id   # optional
   ```
5. Deploy. You'll get a URL like `https://your-project.fastmcp.app/mcp`.

### Add the hosted server to Claude

**Claude Code (CLI):**

```bash
claude mcp add --transport http splitwise https://your-project.fastmcp.app/mcp
```

**Claude Desktop / claude.ai:** Settings → **Connectors** → **Add custom
connector** → paste the `https://your-project.fastmcp.app/mcp` URL. (If the
project has authentication enabled, Claude will walk you through the login.)

The remote-server JSON form (for clients that accept it) is just the URL — no
secrets:

```json
{
  "mcpServers": {
    "splitwise": {
      "url": "https://your-project.fastmcp.app/mcp"
    }
  }
}
```

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
