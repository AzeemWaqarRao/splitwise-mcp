"""Splitwise MCP server — expense tools.

Exposes the essential Splitwise expense endpoints as MCP tools:
list_expenses, get_expense, create_expense, update_expense, delete_expense.

Configuration (environment variables):
  SPLITWISE_API_KEY   required — API key from dev.splitwise.com ("Your apps")
  SPLITWISE_GROUP_ID  optional — default group id used when a tool omits group_id
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

BASE_URL = "https://secure.splitwise.com/api/v3.0"

mcp = FastMCP("splitwise")


def _headers() -> dict[str, str]:
    """Headers of the current HTTP request (lowercased keys), or {} if none.

    Returns {} when running over stdio / outside an HTTP request, in which case
    callers fall back to environment variables.
    """
    try:
        return get_http_headers()
    except Exception:
        return {}


def _api_key() -> str:
    """Per-user Splitwise API key from the request header, else the env default."""
    key = _headers().get("x-splitwise-api-key") or os.environ.get("SPLITWISE_API_KEY")
    if not key:
        raise RuntimeError(
            "No Splitwise API key. Send it in the 'X-Splitwise-Api-Key' header "
            "(remote/multi-user) or set SPLITWISE_API_KEY (local). Get a key at "
            "dev.splitwise.com → Your apps."
        )
    return key


def _default_group_id() -> int | None:
    """Per-user default group id from the request header, else the env default."""
    raw = _headers().get("x-splitwise-group-id") or os.environ.get("SPLITWISE_GROUP_ID")
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(raw)
    except ValueError:
        raise RuntimeError(f"Splitwise group id is not a valid integer: {raw!r}")


def _resolve_group_id(group_id: int | None) -> int:
    """Return the explicit group_id, else the env default, else error."""
    if group_id is not None:
        return group_id
    default = _default_group_id()
    if default is not None:
        return default
    raise ValueError(
        "No group_id provided and SPLITWISE_GROUP_ID is not set. "
        "Pass group_id explicitly (use 0 for a non-group expense)."
    )


def _request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call the Splitwise API and return parsed JSON.

    Raises RuntimeError with a clear message on HTTP errors or on Splitwise
    validation errors (which arrive as 200 responses containing an `errors` block).
    """
    headers = {"Authorization": f"Bearer {_api_key()}"}
    # Drop None values so we only send the fields we mean to.
    if params is not None:
        params = {k: v for k, v in params.items() if v is not None}
    if data is not None:
        data = {k: v for k, v in data.items() if v is not None}

    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        resp = client.request(
            method, path, headers=headers, params=params, data=data
        )

    if resp.status_code >= 400:
        raise RuntimeError(
            f"Splitwise API error {resp.status_code} for {method} {path}: {resp.text}"
        )

    try:
        payload = resp.json()
    except ValueError:
        raise RuntimeError(
            f"Splitwise returned non-JSON response for {method} {path}: {resp.text}"
        )

    # Splitwise reports validation problems as an `errors` object/array on a 200.
    errors = payload.get("errors") if isinstance(payload, dict) else None
    if errors:
        raise RuntimeError(f"Splitwise validation error for {method} {path}: {errors}")

    return payload


def _flatten_users(users: list[dict[str, Any]]) -> dict[str, Any]:
    """Turn a list of user-share dicts into Splitwise's users__{i}__field form fields.

    Each dict may contain: user_id (or email/first_name/last_name), paid_share, owed_share.
    """
    out: dict[str, Any] = {}
    for i, user in enumerate(users):
        for field, value in user.items():
            if value is None:
                continue
            out[f"users__{i}__{field}"] = value
    return out


@mcp.tool()
def list_expenses(
    group_id: int | None = None,
    friend_id: int | None = None,
    dated_after: str | None = None,
    dated_before: str | None = None,
    updated_after: str | None = None,
    updated_before: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List expenses, most recent first.

    When group_id is omitted, the SPLITWISE_GROUP_ID default is used. Pass
    group_id=0 to list expenses across all groups and non-group expenses.
    Date filters (dated_after/before, updated_after/before) accept ISO 8601
    strings, e.g. "2026-01-31T00:00:00Z".
    """
    if group_id is None:
        group_id = _default_group_id()  # may stay None → all groups
    params = {
        "group_id": group_id,
        "friend_id": friend_id,
        "dated_after": dated_after,
        "dated_before": dated_before,
        "updated_after": updated_after,
        "updated_before": updated_before,
        "limit": limit,
        "offset": offset,
    }
    return _request("GET", "/get_expenses", params=params)


@mcp.tool()
def get_expense(expense_id: int) -> dict[str, Any]:
    """Get the full details of a single expense by its id."""
    return _request("GET", f"/get_expense/{expense_id}")


@mcp.tool()
def create_expense(
    cost: str,
    description: str,
    group_id: int | None = None,
    split_equally: bool = True,
    users: list[dict[str, Any]] | None = None,
    date: str | None = None,
    currency_code: str | None = None,
    category_id: int | None = None,
    details: str | None = None,
) -> dict[str, Any]:
    """Create a new expense.

    cost is a decimal string, e.g. "25.00". description is required.

    Splitting:
      - Equal split (default): leave `users` empty; the cost is split evenly
        among everyone in the resolved group (group_id or SPLITWISE_GROUP_ID).
      - Custom split: pass `users`, a list of dicts each like
        {"user_id": 123, "paid_share": "25.00", "owed_share": "12.50"}.
        Identify a user by user_id, or by email/first_name/last_name. The
        paid_share values must sum to cost, and so must the owed_share values.

    date accepts ISO 8601 (e.g. "2026-06-15T00:00:00Z"). currency_code is a
    3-letter code (e.g. "USD"). category_id and details are optional.
    """
    data: dict[str, Any] = {
        "cost": cost,
        "description": description,
        "date": date,
        "currency_code": currency_code,
        "category_id": category_id,
        "details": details,
    }

    if users:
        # Custom split: group_id is still useful context; don't send split_equally.
        if group_id is None:
            group_id = _default_group_id()
        data["group_id"] = group_id
        data.update(_flatten_users(users))
    else:
        # Equal split requires a concrete group_id.
        data["group_id"] = _resolve_group_id(group_id)
        data["split_equally"] = True

    return _request("POST", "/create_expense", data=data)


@mcp.tool()
def update_expense(
    expense_id: int,
    cost: str | None = None,
    description: str | None = None,
    group_id: int | None = None,
    users: list[dict[str, Any]] | None = None,
    date: str | None = None,
    currency_code: str | None = None,
    category_id: int | None = None,
    details: str | None = None,
) -> dict[str, Any]:
    """Update an existing expense. Only provided fields are changed.

    Note: if you pass `users` (custom shares), it overwrites ALL existing
    shares on the expense — include every participant. See create_expense for
    the users format and split rules.
    """
    data: dict[str, Any] = {
        "cost": cost,
        "description": description,
        "group_id": group_id,
        "date": date,
        "currency_code": currency_code,
        "category_id": category_id,
        "details": details,
    }
    if users:
        data.update(_flatten_users(users))
    return _request("POST", f"/update_expense/{expense_id}", data=data)


@mcp.tool()
def delete_expense(expense_id: int) -> dict[str, Any]:
    """Delete an expense by id. Returns {"success": true} on success."""
    return _request("POST", f"/delete_expense/{expense_id}")


if __name__ == "__main__":
    mcp.run()
