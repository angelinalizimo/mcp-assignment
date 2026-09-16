"""
server.py
---------
MCP server exposing a small task-management toolset.

Domain: Personal Productivity (task tracking)
Combination chosen: two tools + one prompt

Tools:
  - add_task:   create a new task
  - list_tasks: list/filter existing tasks

Prompt:
  - daily_summary_prompt: reusable template that asks the LLM to produce
    a prioritized summary of the user's tasks.

Security notes: see task_store.py and README.md for the full explanation
of authentication, input sanitization, and error-disclosure handling.
All security-relevant logic lives in task_store.py; this file only maps
that logic onto the MCP protocol surface.

Server skeleton pattern adapted from the official MCP Python SDK quickstart:
https://github.com/modelcontextprotocol/python-sdk (examples/snippets/servers/fastmcp_quickstart.py)
"""

from mcp.server.fastmcp import FastMCP

import task_store as ts

mcp = FastMCP("TaskManager")


@mcp.tool()
def add_task(auth_token: str, title: str, due_date: str, priority: str = "medium") -> dict:
    """
    Create a new task.

    Args:
        auth_token: Authentication token (required for every call).
        title: Short description of the task (max 200 chars).
        due_date: Due date in YYYY-MM-DD format.
        priority: One of "low", "medium", "high". Defaults to "medium".

    Returns:
        A dict with {"success": bool, "task_id": int, "title": str} on
        success, or {"success": False, "error": str} on failure.
    """
    return ts.add_task(auth_token, title, due_date, priority)


@mcp.tool()
def list_tasks(auth_token: str, status: str = "all") -> dict:
    """
    List tasks, optionally filtered by status.

    Args:
        auth_token: Authentication token (required for every call).
        status: One of "all", "pending", "done". Defaults to "all".

    Returns:
        A dict with {"success": True, "count": int, "tasks": [...]} on
        success, or {"success": False, "error": str} on failure.
    """
    return ts.list_tasks(auth_token, status)


@mcp.prompt()
def daily_summary_prompt() -> str:
    """Generate a prompt asking the assistant to summarize today's tasks."""
    return (
        "Call the list_tasks tool (status='pending') to fetch my current "
        "tasks, then summarize them for me in priority order (high first), "
        "grouping anything due today or overdue at the top."
    )


if __name__ == "__main__":
    mcp.run()