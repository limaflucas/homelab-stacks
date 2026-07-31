#!/usr/bin/env python3
"""Reconcile a Plane project's states with the agentic workflow board topology.

Idempotent: creates missing states, corrects the group/colour of states that
already exist, and removes states that are not part of the topology. Safe to
re-run.

Usage:
    export PLANE_API_KEY=plane_api_...
    ./bootstrap-plane-board.py --workspace devflow --list-projects
    ./bootstrap-plane-board.py --workspace devflow --project <uuid> --dry-run
    ./bootstrap-plane-board.py --workspace devflow --project <uuid> --prune

TLS: prefer running this from inside the overlay, where Plane is reachable
over plain HTTP and no certificate is involved at all:

    docker run --rm -i --network devflow_private \
      -e PLANE_API_KEY -e PLANE_BASE_URL=http://plane:80 \
      python:3-alpine python - --workspace <slug> --project <uuid> --prune \
      < devflow/scripts/bootstrap-plane-board.py

Running it from a workstation against https://plane.homelab requires the
step-ca root in the trust store. --insecure exists as a last resort and
disables certificate verification entirely; do not use it habitually.
"""

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.request

# The board topology. Order here is the intended left-to-right board order.
#
# Every state is owned unambiguously by either the operator or the agent, and
# approval is expressed by *moving the card* rather than by writing a comment
# for something to parse. The four operator gates deliberately share one colour
# so that "the board is waiting on me" is answerable at a glance.
GATE = "#F59E0B"

STATES = [
    ("Inbox",              "backlog",   "#6B7280", "Operator writes the ticket here"),
    ("Refining",           "unstarted", "#3B82F6", "Agent is scoping and asking questions"),
    ("❓ Needs Answer",     "unstarted", GATE,      "GATE 1 — agent is blocked on the operator"),
    ("Ready",              "unstarted", "#14B8A6", "Scope agreed, meets Definition of Ready"),
    ("Planning",           "started",   "#3B82F6", "Agent is producing an implementation plan"),
    ("📋 Plan Review",      "started",   GATE,      "GATE 2 — operator approves the plan"),
    ("In Progress",        "started",   "#6366F1", "Agent is implementing and testing"),
    ("🔍 PR Review",        "started",   GATE,      "GATE 3 — operator reviews the pull request"),
    ("🚀 Deploy Approval",  "started",   GATE,      "GATE 4 — operator approves the release"),
    ("Done",               "completed", "#22C55E", "Merged and deployed"),
    ("⚠️ Blocked",          "cancelled", "#EF4444", "Needs operator intervention"),
]


class Plane:
    def __init__(self, base_url, api_key, insecure=False):
        self.base = base_url.rstrip("/")
        self.key = api_key
        self.ctx = None
        if insecure:
            print("WARNING: TLS verification disabled (--insecure). This traffic "
                  "carries your API key and is open to interception.\n"
                  "         Prefer PLANE_BASE_URL=http://plane:80 from inside "
                  "devflow_private, or trust the step-ca root.", file=sys.stderr)
            self.ctx = ssl.create_default_context()
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE

    def call(self, method, path, body=None):
        url = f"{self.base}/api/v1{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("X-API-Key", self.key)
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, context=self.ctx, timeout=30) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:400]
            raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {detail}") from None
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"{method} {path} -> cannot reach {self.base}: {e.reason}\n"
                "If this is a TLS trust failure against the internal CA, run it "
                "from inside devflow_private with PLANE_BASE_URL=http://plane:80 "
                "(see the module docstring)."
            ) from None

    def paged(self, path):
        """Return every item, following Plane's cursor pagination."""
        out, seen = [], set()
        cursor = None
        while True:
            page = self.call("GET", path + (f"?cursor={cursor}" if cursor else ""))
            if isinstance(page, list):
                return page
            out.extend(page.get("results", []))
            cursor = page.get("next_cursor")
            # next_page_results is the authoritative "keep going" flag; the
            # cursor is echoed back even on the last page.
            if not page.get("next_page_results") or cursor in seen:
                return out
            seen.add(cursor)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("PLANE_BASE_URL", "https://plane.homelab"))
    ap.add_argument("--workspace", default=os.environ.get("PLANE_WORKSPACE"))
    ap.add_argument("--project", default=os.environ.get("PLANE_PROJECT"))
    ap.add_argument("--list-projects", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--insecure", action="store_true", help="skip TLS verification")
    ap.add_argument("--prune", action="store_true",
                    help="delete states that are not part of the topology")
    args = ap.parse_args()

    api_key = os.environ.get("PLANE_API_KEY")
    if not api_key:
        sys.exit("PLANE_API_KEY is not set. Create one in Plane under "
                 "Profile settings -> Personal access tokens.")
    if not args.workspace:
        sys.exit("--workspace (or PLANE_WORKSPACE) is required. It is the slug "
                 "in your Plane URL: https://plane.homelab/<slug>/projects/...")

    plane = Plane(args.base_url, api_key, args.insecure)
    ws = args.workspace

    if args.list_projects:
        for p in plane.paged(f"/workspaces/{ws}/projects/"):
            print(f"{p['id']}  {p['name']}")
        return

    if not args.project:
        sys.exit("--project (or PLANE_PROJECT) is required. "
                 "Run with --list-projects to find the id.")

    base = f"/workspaces/{ws}/projects/{args.project}/states/"
    existing = plane.paged(base)
    by_name = {s["name"]: s for s in existing}
    wanted = {name for name, _, _, _ in STATES}

    created = updated = unchanged = 0

    for seq, (name, group, color, description) in enumerate(STATES, start=1):
        payload = {"name": name, "group": group, "color": color,
                   "description": description, "sequence": seq * 1000}
        cur = by_name.get(name)
        if cur is None:
            print(f"  create  {name}  ({group})")
            if not args.dry_run:
                plane.call("POST", base, payload)
            created += 1
        elif (cur.get("group"), cur.get("color", "").lower()) != (group, color.lower()):
            print(f"  update  {name}  ({cur.get('group')} -> {group})")
            if not args.dry_run:
                plane.call("PATCH", f"{base}{cur['id']}/", payload)
            updated += 1
        else:
            unchanged += 1

    stale = [s for s in existing if s["name"] not in wanted]
    if stale and not args.prune:
        print("\nStates not in the topology (re-run with --prune to remove):")
        for s in stale:
            print(f"  - {s['name']}")
    for s in stale if args.prune else []:
        try:
            print(f"  delete  {s['name']}")
            if not args.dry_run:
                plane.call("DELETE", f"{base}{s['id']}/")
        except RuntimeError as e:
            # Plane refuses to delete a project's default state, and any state
            # that still has work items in it.
            print(f"  SKIPPED {s['name']}: {e}")

    print(f"\ncreated={created} updated={updated} unchanged={unchanged}"
          f"{' (dry run)' if args.dry_run else ''}")

    if not args.dry_run:
        print("\nBoard is now:")
        for s in sorted(plane.paged(base), key=lambda s: s.get("sequence") or 0):
            print(f"  {s['group']:<10} {s['name']}")


if __name__ == "__main__":
    main()
