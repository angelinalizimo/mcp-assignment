# Task Manager MCP Server

A local MCP (Model Context Protocol) server that exposes simple task-tracking functionality to MCP clients such as Claude Desktop.

**Domain:** Personal Productivity (task tracking)
**Combination implemented:** two tools + one prompt

## What it does

| Type   | Name                   | Description                                              |
|--------|------------------------|------------------------------------------------------------|
| Tool   | `add_task`             | Create a new task (title, due date, priority).             |
| Tool   | `list_tasks`           | List tasks, optionally filtered by status.                 |
| Prompt | `daily_summary_prompt` | Reusable prompt template asking the model to summarize the user's pending tasks. |

## Architecture

```
Claude Desktop (MCP client)
        |  stdio transport
        v
   server.py  (MCP protocol layer -- FastMCP tool/prompt decorators)
        |
        v
  task_store.py  (business logic: auth check, input validation,
                   parameterized SQL, safe error handling)
        |
        v
   tasks.db (SQLite)          server.log (local-only detailed error log)
```

See `architecture_diagram.png` for the visual version.

## Setup

Requires Python 3.11+ and either conda or uv. These steps use conda (this project was built and tested with Anaconda on Windows).

```
cd mcp-assignment
conda create -n mcp-env python=3.11 -y
conda activate mcp-env
pip install -r requirements.txt
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(16))"
```

Paste the output of that last command into `.env` as `API_TOKEN`.

## Running the exploit tests

```
$env:API_TOKEN="<the same value as in .env>"
python test_exploits.py
```

This runs three checks and prints `PASS` for each:
1. A SQL-injection payload in `title` is stored as inert text -- the `tasks` table is not dropped.
2. A wrong `auth_token` is rejected with a generic message.
3. A forced internal error (e.g. database unavailable) returns a generic message to the caller, while the full stack trace is written to `server.log` only.

## Connecting to Claude Desktop

**Note:** on this project's dev machine, the current (Microsoft-Store-packaged) version of Claude Desktop reads its config from `%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\claude_desktop_config.json` -- not the older `%APPDATA%\Claude\claude_desktop_config.json` path some documentation references. If Claude Desktop doesn't pick up the config, check Settings -> Developer -> "Edit config" inside the app itself to find the exact path it's reading from on your machine.

1. Open `claude_desktop_config.json` in this repo.
2. Replace the `command` path with the full path to the Python interpreter inside your `mcp-env` environment (find it with `where python` after activating the environment).
3. Replace the `args` path with this project's actual absolute path to `server.py`.
4. Replace the `API_TOKEN` value with the same secret you used in `.env`.
5. Merge this `mcpServers` block into your Claude Desktop config (use Settings -> Developer -> "Edit config" in the app to find/open it directly, rather than guessing the path).
6. Fully quit and reopen Claude Desktop. Under Settings -> Developer, the `task-manager` server should show status **Running**.

## Security / Best Practices

Authentication (required by the assignment, not one of the two graded practices): every tool call requires an `auth_token` parameter matched against the `API_TOKEN` environment variable. Missing or wrong tokens are rejected with a generic message -- see `task_store._check_auth`.

### Best Practice 1: Input Sanitization
All SQL queries use parameterized statements (`?` placeholders), never string formatting/f-strings. Free-text fields (`status`, `priority`) are additionally checked against a fixed whitelist before use. See `task_store.py`, functions `_validate_*` and the `INSERT`/`SELECT` statements in `add_task` / `list_tasks`.

**Exploit test:** `test_sql_injection_blocked` in `test_exploits.py` submits a title of `hack'); DROP TABLE tasks; --` and verifies the `tasks` table still exists and the payload was stored as a literal string, not executed.

### Best Practice 2: Error Disclosure
Any exception that isn't an expected `AuthError`/`ValidationError` is caught, logged with full detail (stack trace, exception type) to `server.log` only, and the caller receives a single generic message: `"An internal error occurred. Please try again."` No file paths, SQL text, or stack traces are ever returned over MCP.

**Exploit test:** `test_error_disclosure_safe` in `test_exploits.py` forces an internal `sqlite3.OperationalError` and asserts none of `Traceback`, `sqlite3`, the real DB path, or the exception class name appear in the response returned to the caller.

## Code attribution

The FastMCP server skeleton (`FastMCP(...)`, `@mcp.tool()`, `@mcp.prompt()` usage pattern) is adapted from the official MCP Python SDK quickstart example: https://github.com/modelcontextprotocol/python-sdk (`examples/snippets/servers/fastmcp_quickstart.py`). All business logic in `task_store.py` and the tests in `test_exploits.py` are original.

## Limitations

See `REFLECTION.md` for a full discussion of limitations and possible improvements.