#!/usr/bin/env python3
"""Generate the stat cards for the QW1CKS profile README.

Design goals
------------
* zero third-party services - the cards cannot degrade into a "rate limited"
  placeholder or a 402/503 image, because we render them ourselves;
* zero dependencies - Python standard library only, so the workflow needs
  no pip install step;
* values come straight from the GitHub REST API at build time.

Outputs
-------
    assets/generated/dashboard.svg   stats + language breakdown, 860x252
    assets/generated/stamp.svg       build timestamp, 860x28

Run locally:
    python scripts/generate_stats.py            # unauthenticated, rate limited
    GITHUB_TOKEN=ghp_... python scripts/generate_stats.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

# --------------------------------------------------------------------------- #
# configuration
# --------------------------------------------------------------------------- #

USER = os.environ.get("GITHUB_USER", "QW1CKS")
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
API = "https://api.github.com"

OUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "generated"

# palette - keep in sync with the README theme
BG = "#0d1117"
BORDER = "#21262d"
ACCENT = "#00ff9c"
ACCENT_DIM = "#00c97a"
TEXT = "#c9d1d9"
MUTED = "#8b949e"
DIM = "#6e7681"
RED = "#ff5f56"
YELLOW = "#ffbd2e"
GREEN = "#27c93f"

MONO = "'JetBrains Mono','SFMono-Regular',Consolas,'Liberation Mono',monospace"
LANG_LIMIT = 5

# order of the featured-work grid; missing repos are skipped silently
FEATURED = ("AnyPS5", "KytyPS5", "anti-private-equity-slop", "rust-calc")


# --------------------------------------------------------------------------- #
# github api
# --------------------------------------------------------------------------- #


def get(path: str):
    req = urllib.request.Request(f"{API}{path}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", f"{USER}-profile-card-generator")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def collect() -> dict:
    user = get(f"/users/{USER}")

    repos = get(f"/users/{USER}/repos?per_page=100&sort=pushed")
    repos = [r for r in repos if not r.get("archived")]

    languages: dict[str, int] = {}
    meta: dict[str, dict] = {}
    for repo in repos:
        try:
            per_repo = {
                name: int(size)
                for name, size in get(f"/repos/{USER}/{repo['name']}/languages").items()
            }
            for name, size in per_repo.items():
                languages[name] = languages.get(name, 0) + size
            primary = max(per_repo.items(), key=lambda kv: kv[1])[0] if per_repo else ""
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as exc:
            print(f"warn: languages for {repo['name']}: {exc}", file=sys.stderr)
            primary = repo.get("language") or ""

        meta[repo["name"]] = {
            "description": repo.get("description") or "no description yet",
            "stars": repo.get("stargazers_count", 0),
            "fork": bool(repo.get("fork")),
            "language": primary,
        }

    joined = datetime.strptime(user["created_at"], "%Y-%m-%dT%H:%M:%SZ")

    return {
        "login": user["login"],
        "repos": user["public_repos"],
        "commits": commit_count(),
        "stars": sum(r.get("stargazers_count", 0) for r in repos),
        "followers": user["followers"],
        "joined": joined.strftime("%Y-%m"),
        "languages": top_languages(languages),
        "featured": [(name, meta[name]) for name in FEATURED if name in meta],
    }


def commit_count() -> int | None:
    """Public commit count for the user, or None if the search API refuses."""
    try:
        return int(get(f"/search/commits?q=author:{USER}&per_page=1").get("total_count", 0))
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, TypeError) as exc:
        print(f"warn: commit search unavailable: {exc}", file=sys.stderr)
        return None


def top_languages(byte_counts: dict[str, int]) -> list[tuple[str, int]]:
    """Top N real languages by byte volume, ignoring build/markup noise."""
    noise = {
        "CMake", "Makefile", "Batchfile", "Shell", "PowerShell", "Dockerfile",
        "HTML", "CSS", "SCSS", "Less", "MDX", "Roff", "TeX", "Meson",
        "Objective-C", "Rich Text Format", "JSON", "YAML", "TOML", "Nix",
    }
    cleaned = {k: v for k, v in byte_counts.items() if v > 0 and k not in noise}
    if not cleaned:  # never render an empty card
        cleaned = {k: v for k, v in byte_counts.items() if v > 0}
    ranked = sorted(cleaned.items(), key=lambda kv: kv[1], reverse=True)
    return ranked[:LANG_LIMIT]


# --------------------------------------------------------------------------- #
# svg helpers
# --------------------------------------------------------------------------- #


def text(x, y, value, *, size=13, fill=TEXT, weight="400", anchor="start", opacity=None):
    extra = f' opacity="{opacity}"' if opacity is not None else ""
    return (
        f'<text x="{x}" y="{y}" font-family="{MONO}" font-size="{size}" '
        f'fill="{fill}" font-weight="{weight}" text-anchor="{anchor}"{extra}>'
        f"{escape(str(value))}</text>"
    )


def chrome(width: int, title: str) -> str:
    return f"""  <defs>
    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="2.6" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    <linearGradient id="fill" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{ACCENT_DIM}"/>
      <stop offset="1" stop-color="{ACCENT}"/>
    </linearGradient>
  </defs>
  <rect x="0.5" y="0.5" width="{width - 1}" height="252" rx="10"
        fill="{BG}" stroke="{BORDER}"/>
  <rect x="1" y="1" width="{width - 2}" height="36" rx="10" fill="#11161d"/>
  <rect x="1" y="26" width="{width - 2}" height="11" fill="#11161d"/>
  <circle cx="20" cy="19" r="4.5" fill="{RED}"/>
  <circle cx="36" cy="19" r="4.5" fill="{YELLOW}"/>
  <circle cx="52" cy="19" r="4.5" fill="{GREEN}"/>
{text(width - 18, 23, title, size=11, fill=DIM, anchor="end")}
  <line x1="1" y1="37.5" x2="{width - 1}" y2="37.5" stroke="{BORDER}"/>"""


def prompt(x, y, command: str) -> str:
    return (
        text(x, y, "$", size=13, fill=ACCENT, weight="700")
        + text(x + 14, y, f" {command}", size=13, fill=TEXT)
    )


def dashboard(data: dict) -> str:
    w, h = 860, 252
    split = 430
    left = 26
    right = 452

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" role="img" aria-label="GitHub statistics for {escape(data["login"])}">',
        chrome(w, f"{data['login'].lower()}@sys: ~"),
        prompt(left, 68, "whoami --stats"),
        f'  <line x1="{split}" y1="52" x2="{split}" y2="{h - 16}" stroke="{BORDER}"/>',
    ]

    rows = [("repos", data["repos"])]
    if data.get("commits") is not None:
        rows.append(("commits", data["commits"]))
    rows += [
        ("stars earned", data["stars"]),
        ("followers", data["followers"]),
        ("since", data["joined"]),
    ]
    y = 100
    for label, value in rows:
        parts.append(text(left, y, label, size=12.5, fill=MUTED))
        parts.append(text(left + 132, y, value, size=12.5, fill=TEXT, weight="600"))
        y += 27

    parts.append(prompt(right, 68, f"langstat --top {len(data['languages'])}"))

    bar_x = right + 96
    bar_w = 224
    pct_x = 838

    total = sum(v for _, v in data["languages"]) or 1
    y = 100
    for name, size in data["languages"]:
        pct = size * 100 / total
        width = max(4.0, bar_w * pct / 100)
        parts.append(text(right, y, name[:11], size=12.5, fill=TEXT))
        parts.append(
            f'  <rect x="{bar_x}" y="{y - 9}" width="{bar_w}" height="8" rx="4" fill="#161b22"/>'
        )
        parts.append(
            f'  <rect x="{bar_x}" y="{y - 9}" width="{width:.1f}" height="8" rx="4" '
            f'fill="url(#fill)" filter="url(#glow)"/>'
        )
        parts.append(text(pct_x, y, f"{pct:.1f}%", size=11.5, fill=MUTED, anchor="end"))
        y += 27

    parts.append(text(left, h - 16, "rendered from the github rest api", size=10.5, fill=DIM))
    parts.append(text(w - 18, h - 16, "rebuilt nightly", size=10.5, fill=DIM, anchor="end"))
    parts.append("</svg>")
    return "\n".join(parts)


def wrap(value: str, width: int, max_lines: int = 2) -> list[str]:
    """Greedy word wrap, then ellipsis if it still overflows."""
    lines: list[str] = []
    current = ""
    for word in value.split():
        candidate = f"{current} {word}".strip()
        if len(candidate) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: width - 1].rstrip() + "\u2026"
    return lines


def repo_card(name: str, meta: dict, x: int, y: int, w: int = 406, h: int = 118) -> list[str]:
    parts = [
        f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{BG}" stroke="{BORDER}"/>',
        f'  <rect x="{x}" y="{y + 12}" width="3" height="{h - 24}" rx="1.5" fill="{ACCENT}" opacity="0.8"/>',
        text(x + 18, y + 30, name, size=14, fill=ACCENT, weight="600"),
    ]

    for i, line in enumerate(wrap(meta["description"], 52)):
        parts.append(text(x + 18, y + 52 + i * 17, line, size=11.5, fill=MUTED))

    base = y + h - 16
    cursor = x + 18
    if meta["language"]:
        parts.append(f'  <circle cx="{cursor + 3}" cy="{base - 4}" r="3.5" fill="{ACCENT_DIM}"/>')
        parts.append(text(cursor + 13, base, meta["language"], size=11, fill=TEXT))
        cursor += 13 + len(meta["language"]) * 6.6 + 16
    if meta["fork"]:
        parts.append(text(cursor, base, "fork", size=11, fill=DIM))
    parts.append(text(x + w - 18, base, f"{meta['stars']} \u2605", size=11, fill=MUTED, anchor="end"))
    return parts


def repos_card(data: dict) -> str:
    w, h = 860, 278
    card_w, card_h = 406, 118
    positions = [(14, 14), (440, 14), (14, 146), (440, 146)]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" role="img" aria-label="featured repositories">'
    ]
    for (name, meta), (x, y) in zip(data["featured"], positions):
        parts.extend(repo_card(name, meta, x, y, card_w, card_h))
    parts.append("</svg>")
    return "\n".join(parts)


def stamp() -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="860" height="28" viewBox="0 0 860 28" '
        f'role="img" aria-label="last refreshed {now}">\n'
        + text(430, 18, f"// last refresh: {now}", size=11, fill=DIM, anchor="middle")
        + "\n</svg>\n"
    )


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        data = collect()
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError) as exc:
        # leave the previously generated assets in place rather than shipping
        # a half-empty card
        print(f"error: could not reach the GitHub API: {exc}", file=sys.stderr)
        return 1

    (OUT_DIR / "dashboard.svg").write_text(dashboard(data), encoding="utf-8")
    (OUT_DIR / "repos.svg").write_text(repos_card(data), encoding="utf-8")
    (OUT_DIR / "stamp.svg").write_text(stamp(), encoding="utf-8")

    print(
        "cards written - "
        f"{data['repos']} repos, {data['stars']} stars, {data['followers']} followers, "
        f"langs: {', '.join(n for n, _ in data['languages'])}, "
        f"featured: {', '.join(n for n, _ in data['featured'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
