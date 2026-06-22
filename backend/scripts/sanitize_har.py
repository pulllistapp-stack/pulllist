"""Sanitize a Target HAR file → keep only Target API calls, redact PII.

Usage:
    python sanitize_har.py path/to/target.har

Output:
    target.sanitized.json  (next to input)
    target.summary.md      (human-readable summary)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# URL patterns we care about (Target API endpoints)
KEEP_URL_PATTERNS = [
    r"carts\.target\.com",
    r"co-checkout-pcs\.target\.com",
    r"checkout\.target\.com",
    r"redsky\.target\.com.*pdp_fulfillment",
    r"redsky\.target\.com.*store_search",
    r"redsky\.target\.com.*nearby",
    r"api\.target\.com",
    r"target\.com/.+\.target\.com",
    r"target\.com/api/",
]

# URLs to skip even if matching
SKIP_URL_PATTERNS = [
    r"\.(png|jpg|jpeg|gif|webp|svg|ico|woff2?|ttf|css|js|map)(\?|$)",
    r"google-analytics",
    r"googletagmanager",
    r"adsystem",
    r"doubleclick",
    r"facebook\.com",
    r"branch\.io",
    r"segment\.io",
    r"datadog",
    r"sentry",
    r"newrelic",
    r"/_bm/",  # Akamai sensor (huge, not useful for our purposes)
]

# Headers to fully redact (keep name, blank value)
REDACT_HEADERS = {
    "cookie",
    "set-cookie",
    "authorization",
    "x-csrf-token",
    "x-xsrf-token",
}

# Headers to partially preserve (keep format hint)
TRUNCATE_HEADERS = {
    "x-api-key",
    "x-application-version",
    "x-application-name",
}

# JSON payload keys whose values get redacted
PII_KEY_PATTERNS = [
    r"first_?name",
    r"last_?name",
    r"middle_?name",
    r"full_?name",
    r"email",
    r"phone",
    r"mobile",
    r"address_?line",
    r"street",
    r"city",
    r"date_?of_?birth",
    r"dob",
    r"ssn",
    r"tax_?id",
    r"card_?number",
    r"cc_?number",
    r"cvv",
    r"cvc",
    r"security_?code",
    r"account_?number",
    r"routing_?number",
    r"password",
    # Target-specific
    r"guest_?id",
    r"visitor_?id",
    r"member_?id",
    r"user_?id",
    r"profile_?id",
    r"address_?id",  # 이건 봇이 알아야 하지만 너 ID 라 노출 X
    r"payment_?method_?id",
]

# Value patterns to redact (regex on string values)
PII_VALUE_PATTERNS = [
    # Credit cards (any 13-19 digit sequence with optional spaces/dashes)
    (r"\b(?:\d[ -]*?){13,19}\b", "[CARD_REDACTED]"),
    # Email
    (r"[\w.+-]+@[\w-]+\.[\w.-]+", "[EMAIL_REDACTED]"),
    # Phone (US format)
    (r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[PHONE_REDACTED]"),
    # ZIP code 12345 or 12345-6789 (keep first 2 digits for region context)
    (r"\b(\d{2})\d{3}(?:-\d{4})?\b", r"\1***"),
]


def url_matches(url: str, patterns: list[str]) -> bool:
    return any(re.search(p, url, re.IGNORECASE) for p in patterns)


def should_keep(url: str, method: str, status: int) -> bool:
    if url_matches(url, SKIP_URL_PATTERNS):
        return False
    if not url_matches(url, KEEP_URL_PATTERNS):
        return False
    # Skip preflight + redirects for noise reduction
    if method == "OPTIONS":
        return False
    if status in (301, 302, 304):
        return False
    return True


def redact_string(value: str) -> str:
    """Apply PII value patterns to a string."""
    for pattern, replacement in PII_VALUE_PATTERNS:
        value = re.sub(pattern, replacement, value)
    return value


def redact_json(node: Any, path: str = "") -> Any:
    """Recursively walk a JSON structure, redacting PII fields and patterns."""
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            key_lower = k.lower().replace("-", "_")
            # Match PII key patterns
            is_pii_key = any(re.fullmatch(p, key_lower) for p in PII_KEY_PATTERNS)
            if is_pii_key:
                if isinstance(v, str):
                    out[k] = f"[REDACTED_{k}]"
                elif isinstance(v, (int, float, bool)):
                    out[k] = "[REDACTED]"
                elif isinstance(v, (dict, list)):
                    out[k] = "[REDACTED_OBJECT]"
                else:
                    out[k] = None
            else:
                out[k] = redact_json(v, f"{path}.{k}")
        return out
    elif isinstance(node, list):
        return [redact_json(item, f"{path}[]") for item in node]
    elif isinstance(node, str):
        return redact_string(node)
    else:
        return node


def redact_headers(headers: list[dict]) -> list[dict]:
    out = []
    for h in headers:
        name = h.get("name", "").lower()
        value = h.get("value", "")
        if name in REDACT_HEADERS:
            out.append({"name": h["name"], "value": "[REDACTED]"})
        elif name in TRUNCATE_HEADERS:
            # Keep first 8 chars + hint at format
            hint = value[:8] + "..." if len(value) > 8 else value
            out.append({"name": h["name"], "value": f"{hint} ({len(value)} chars)"})
        else:
            out.append({"name": h["name"], "value": redact_string(value)})
    return out


def parse_body(body_text: str) -> Any:
    if not body_text:
        return None
    try:
        return json.loads(body_text)
    except (json.JSONDecodeError, TypeError):
        return body_text


def serialize_body(body: Any) -> str:
    if body is None:
        return ""
    if isinstance(body, str):
        return body
    return json.dumps(body, indent=2, ensure_ascii=False)


def process_entry(entry: dict) -> dict | None:
    req = entry.get("request", {})
    resp = entry.get("response", {})
    url = req.get("url", "")
    method = req.get("method", "")
    status = resp.get("status", 0)

    if not should_keep(url, method, status):
        return None

    # Request body
    req_body_text = req.get("postData", {}).get("text", "")
    req_body = parse_body(req_body_text)
    req_body = redact_json(req_body) if isinstance(req_body, (dict, list)) else req_body

    # Response body
    resp_body_text = resp.get("content", {}).get("text", "")
    resp_body = parse_body(resp_body_text)
    resp_body = redact_json(resp_body) if isinstance(resp_body, (dict, list)) else resp_body

    return {
        "method": method,
        "url": redact_string(url),
        "status": status,
        "request": {
            "headers": redact_headers(req.get("headers", [])),
            "body": req_body,
        },
        "response": {
            "headers": redact_headers(resp.get("headers", [])),
            "body": resp_body,
        },
        "duration_ms": int(entry.get("time", 0)),
    }


def summarize(entries: list[dict]) -> str:
    lines = ["# HAR Summary\n"]
    lines.append(f"Total relevant requests: **{len(entries)}**\n")
    lines.append("## Endpoints hit\n")

    by_url: dict[str, list[dict]] = {}
    for e in entries:
        # Strip query string for grouping
        base = e["url"].split("?")[0]
        by_url.setdefault(base, []).append(e)

    for url, calls in sorted(by_url.items()):
        methods = sorted({c["method"] for c in calls})
        statuses = sorted({c["status"] for c in calls})
        lines.append(f"- `{url}`")
        lines.append(f"  - Methods: {', '.join(methods)}")
        lines.append(f"  - Statuses: {', '.join(str(s) for s in statuses)}")
        lines.append(f"  - Count: {len(calls)}")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("har_file", help="Path to the .har file from DevTools")
    args = parser.parse_args()

    har_path = Path(args.har_file)
    if not har_path.exists():
        print(f"Error: {har_path} not found", file=sys.stderr)
        sys.exit(1)

    print(f"Loading {har_path.name}…")
    with har_path.open(encoding="utf-8") as f:
        har = json.load(f)

    raw_entries = har.get("log", {}).get("entries", [])
    print(f"Total entries in HAR: {len(raw_entries)}")

    processed = []
    for entry in raw_entries:
        result = process_entry(entry)
        if result:
            processed.append(result)

    print(f"Kept after filtering: {len(processed)}")

    # Write sanitized JSON
    out_path = har_path.with_suffix(".sanitized.json")
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(processed, f, indent=2, ensure_ascii=False)
    print(f"Wrote {out_path.name}")

    # Write summary
    summary_path = har_path.with_suffix(".summary.md")
    with summary_path.open("w", encoding="utf-8") as f:
        f.write(summarize(processed))
    print(f"Wrote {summary_path.name}")

    size_kb = out_path.stat().st_size / 1024
    print(f"\nDone. Sanitized file is {size_kb:.1f} KB")
    print(f"Review {out_path.name} before sharing — make sure no PII slipped through.")


if __name__ == "__main__":
    main()
