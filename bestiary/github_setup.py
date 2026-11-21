"""Create the farolito demo repository and its issue on GitHub (for encounter 8 online).

Needs GITHUB_TOKEN with permission to create the repo (or create it yourself first)
and Contents + Issues + Pull requests read/write on it.
"""

from __future__ import annotations

import base64
import json

import httpx
from rich.console import Console

from bestiary.config import GITHUB_STATE, STATE_DIR, UPSTREAM_TEMPLATE, settings

API = "https://api.github.com"


def setup(full_name: str, private: bool = True) -> int:
    console = Console()
    s = settings()
    if not s.github_token:
        console.print("[red]Set GITHUB_TOKEN first (in .env or the environment).[/]")
        return 1
    owner, name = full_name.split("/", 1)
    http = httpx.Client(
        base_url=API,
        timeout=30,
        headers={"Authorization": f"Bearer {s.github_token}", "Accept": "application/vnd.github+json"},
    )
    me = http.get("/user").json()["login"]
    create_url = "/user/repos" if owner == me else f"/orgs/{owner}/repos"
    r = http.post(create_url, json={"name": name, "private": private, "description": "Toy upstream project for Agentic Bestiary"})
    if r.status_code == 201:
        console.print(f"created {full_name}")
    elif r.status_code == 422:
        console.print(f"{full_name} already exists, reusing it")
    else:
        console.print(f"[red]could not create repo: {r.status_code} {r.text[:200]}[/]")
        return 1

    for path in sorted(UPSTREAM_TEMPLATE.rglob("*")):
        if not path.is_file() or path.name == "issues.json" or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(UPSTREAM_TEMPLATE).as_posix()
        existing = http.get(f"/repos/{full_name}/contents/{rel}")
        payload = {"message": f"add {rel}", "content": base64.b64encode(path.read_bytes()).decode()}
        if existing.status_code == 200:
            continue
        r = http.put(f"/repos/{full_name}/contents/{rel}", json=payload)
        if r.status_code >= 400:
            console.print(f"[red]upload {rel}: {r.status_code} {r.text[:200]}[/]")
            return 1
        console.print(f"uploaded {rel}")

    issue = json.loads((UPSTREAM_TEMPLATE / "issues.json").read_text())[0]
    r = http.post(f"/repos/{full_name}/issues", json={"title": issue["title"], "body": issue["body"]})
    if r.status_code >= 400:
        console.print(f"[red]create issue: {r.status_code} {r.text[:200]}[/]")
        return 1
    number = r.json()["number"]
    STATE_DIR.mkdir(exist_ok=True)
    GITHUB_STATE.write_text(json.dumps({"repo": full_name, "issue_number": number}, indent=2))
    console.print(f"issue #{number}: {r.json()['html_url']}")
    console.print("\nAdd to .env:\n  BESTIARY_FORGE=github\n  BESTIARY_GITHUB_REPO=" + full_name)
    console.print("Recommended: protect the main branch in the repo settings.")
    return 0
