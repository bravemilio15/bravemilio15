#!/usr/bin/env python3
"""
cards.py - render the GitHub activity and language cards as SVGs. Stdlib only.

These are files in this repo, so they keep rendering when the public
github-readme-stats instances go down.

    GITHUB_TOKEN=... python scripts/cards.py --user bravemilio15 --out assets

Writes <out>/stats-{dark,light}.svg and <out>/languages-{dark,light}.svg.

With a personal access token (repo + read:user) the numbers include private
repositories. With the workflow's built-in GITHUB_TOKEN they cover public
repositories only. Languages listed in assets/languages.json under "exclude"
are left out of the language card (generated code, notebooks, docs).

--fixture <file.json> renders from saved data instead of calling the API.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

API = "https://api.github.com/graphql"

THEMES = {
    "dark": {"bg": "#0d1117", "border": "#30363d", "title": "#58a6ff",
             "text": "#c9d1d9", "muted": "#8b949e", "value": "#e6edf3", "track": "#21262d"},
    "light": {"bg": "#ffffff", "border": "#d0d7de", "title": "#0969da",
              "text": "#24292f", "muted": "#57606a", "value": "#1f2328", "track": "#eaeef2"},
}

QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    pullRequests { totalCount }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      contributionCalendar { totalContributions }
    }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100, after: $after) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        languages(first: 12, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def gql(token: str, variables: dict) -> dict:
    req = urllib.request.Request(API, data=json.dumps({"query": QUERY, "variables": variables}).encode(),
                                 headers={"Authorization": f"bearer {token}", "User-Agent": "cards.py"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = json.load(r)
    if body.get("errors"):
        raise SystemExit(f"GraphQL error: {body['errors']}")
    return body["data"]["user"]


def fetch(user: str, token: str) -> dict:
    langs: dict[str, dict] = {}
    after, first = None, None
    while True:
        u = gql(token, {"login": user, "after": after})
        first = first or u
        for repo in u["repositories"]["nodes"]:
            for e in repo["languages"]["edges"]:
                n = e["node"]["name"]
                langs.setdefault(n, {"size": 0, "color": e["node"]["color"] or "#8b949e"})
                langs[n]["size"] += e["size"]
        page = u["repositories"]["pageInfo"]
        if not page["hasNextPage"]:
            break
        after = page["endCursor"]
    cc = first["contributionsCollection"]
    return {
        "repos": first["repositories"]["totalCount"],
        "commits": cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
        "contributions": cc["contributionCalendar"]["totalContributions"],
        "prs": first["pullRequests"]["totalCount"],
        "languages": langs,
    }


def card(theme: str, width: int, height: int, title: str, body: list[str]) -> str:
    c = THEMES[theme]
    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'font-family="-apple-system, Segoe UI, Helvetica, Arial, sans-serif">',
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" fill="{c["bg"]}" stroke="{c["border"]}"/>',
        f'<text x="24" y="38" font-size="17" font-weight="600" fill="{c["title"]}">{title}</text>',
        *body, "</svg>"])


def stats_svg(theme: str, d: dict) -> str:
    c = THEMES[theme]
    tiles = [("Repositories", d["repos"]), ("Commits (past year)", d["commits"]),
             ("Contributions (past year)", d["contributions"]), ("Pull requests", d["prs"])]
    body = []
    for i, (label, value) in enumerate(tiles):
        x, y = 24 + (i % 2) * 220, 66 + (i // 2) * 70
        body.append(f'<text x="{x}" y="{y + 26}" font-size="26" font-weight="700" fill="{c["value"]}">{value:,}</text>')
        body.append(f'<text x="{x}" y="{y + 48}" font-size="13" fill="{c["muted"]}">{label}</text>')
    return card(theme, 460, 210, "GitHub activity", body)


def languages_svg(theme: str, d: dict, exclude: set[str], top: int = 8) -> str:
    c = THEMES[theme]
    items = sorted(((n, v) for n, v in d["languages"].items() if n not in exclude), key=lambda kv: -kv[1]["size"])
    items = items[:top]
    total = sum(v["size"] for _, v in items) or 1
    body, x, bar_w = [], 24.0, 412
    body.append(f'<clipPath id="bar"><rect x="24" y="58" width="{bar_w}" height="10" rx="5"/></clipPath>')
    body.append(f'<rect x="24" y="58" width="{bar_w}" height="10" rx="5" fill="{c["track"]}"/>')
    body.append('<g clip-path="url(#bar)">')
    for _, v in items:
        w = bar_w * v["size"] / total
        body.append(f'<rect x="{x:.1f}" y="58" width="{w + 0.5:.1f}" height="10" fill="{v["color"]}"/>')
        x += w
    body.append("</g>")
    for i, (name, v) in enumerate(items):
        cx, cy = 24 + (i % 2) * 220, 98 + (i // 2) * 27
        pct = 100 * v["size"] / total
        body.append(f'<circle cx="{cx + 5}" cy="{cy - 4}" r="5" fill="{v["color"]}"/>')
        body.append(f'<text x="{cx + 18}" y="{cy}" font-size="13" fill="{c["text"]}">{name} '
                    f'<tspan fill="{c["muted"]}">{pct:.1f}%</tspan></text>')
    return card(theme, 460, 210, "Most used languages", body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="bravemilio15")
    ap.add_argument("--out", default="assets")
    ap.add_argument("--config", default="assets/languages.json")
    ap.add_argument("--fixture")
    args = ap.parse_args()

    if args.fixture:
        data = json.loads(Path(args.fixture).read_text())
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            sys.exit("GITHUB_TOKEN is not set")
        data = fetch(args.user, token)

    exclude = set(json.loads(Path(args.config).read_text()).get("exclude", [])) if Path(args.config).exists() else set()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        (out / f"stats-{theme}.svg").write_text(stats_svg(theme, data), encoding="utf-8")
        (out / f"languages-{theme}.svg").write_text(languages_svg(theme, data, exclude), encoding="utf-8")
    print(f"repos={data['repos']} commits={data['commits']} contributions={data['contributions']} prs={data['prs']}")


if __name__ == "__main__":
    main()
