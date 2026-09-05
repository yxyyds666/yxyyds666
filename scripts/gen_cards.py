#!/usr/bin/env python3
"""把仓库信息渲染成 tokyonight 配色的 SVG 卡片，供主页 README 引用。

github-readme-stats 的公共实例已经 DEPLOYMENT_PAUSED，pin 卡片拿不到了，
所以这里自己画卡片并提交进仓库 —— 图片不会挂，数据靠 Actions 定时刷新。
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import urllib.error
import urllib.request
from xml.sax.saxutils import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "scripts" / "cards.json").read_text("utf-8"))
OUT_DIR = ROOT / CONFIG["outDir"]

# tokyonight（与 github-readme-stats 的同名主题取色一致）
BG, BORDER = "#1a1b26", "#3b4261"
TITLE, TEXT, ICON, MUTED = "#70a5fd", "#38bdae", "#bf91f3", "#a9b1d6"
FONT = "-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,PingFang SC,Microsoft YaHei,sans-serif"

W, H, PAD = 420, 132, 24
LINE_MAX = 2
NO_LINE_START = "，。、；：！？）」》”’·…%"

ICONS = {
    "repo": "M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z",
    "star": "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z",
    "fork": "M5 5.372v.878c0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75v-.878a2.25 2.25 0 1 1 1.5 0v.878a2.25 2.25 0 0 1-2.25 2.25h-1.5v2.128a2.251 2.251 0 1 1-1.5 0V8.5h-1.5A2.25 2.25 0 0 1 3.5 6.25v-.878a2.25 2.25 0 1 1 1.5 0ZM5 3.25a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0Zm6.75.75a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm-3 8.75a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0Z",
}

LANG_COLORS = {
    "Swift": "#F05138", "Python": "#3572A5", "Makefile": "#427819", "C": "#555555",
    "C++": "#f34b7d", "Objective-C": "#438eff", "Shell": "#89e051", "Kotlin": "#A97BFF",
    "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "Vue": "#41b883", "Java": "#b07219",
    "HTML": "#e34c26", "SCSS": "#c6538c", "Go": "#00ADD8", "Rust": "#dea584",
}


def api(path: str) -> dict:
    req = urllib.request.Request(
        "https://api.github.com" + path,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "profile-card-generator"},
    )
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def width_of(s: str, size: float) -> float:
    """粗略估算宽度：CJK 按一个字宽算，ASCII 按 0.52 字宽算。"""
    return sum(size if ord(c) > 0x2E80 else size * 0.52 for c in s)


def tokenize(s: str) -> list:
    """CJK 逐字断行，ASCII 单词整体不拆。"""
    out, buf = [], ""
    for ch in s:
        if ord(ch) > 0x2E80 or ch == " ":
            if buf:
                out.append(buf)
                buf = ""
            out.append(ch)
        else:
            buf += ch
    if buf:
        out.append(buf)
    return out


def wrap(s: str, size: float, limit: float, max_lines: int) -> list:
    """断行，并且不让中文标点掉到行首（悬挂标点）。"""
    lines, cur = [], ""
    for tok in tokenize(s):
        cand = cur + tok
        if width_of(cand.strip(), size) > limit and cur.strip():
            if tok in NO_LINE_START:
                lines.append((cur + tok).strip())
                cur = ""
            else:
                lines.append(cur.strip())
                cur = "" if tok == " " else tok
            if len(lines) == max_lines:
                cur = ""
                break
        else:
            cur = cand
    if len(lines) < max_lines and cur.strip():
        lines.append(cur.strip())
    if len(lines) == max_lines and width_of(lines[-1], size) > limit:
        lines[-1] = lines[-1][:-1].rstrip("，。、；：") + "…"
    return lines


def icon(name: str, x: float, y: float, fill: str, size: float = 16) -> str:
    return (
        f'<g transform="translate({x:g},{y:g}) scale({size / 16:g})" fill="{fill}">'
        f'<path d="{ICONS[name]}"/></g>'
    )


def txt(x: float, y: float, s: str, size: float, weight: int, fill: str) -> str:
    """内联样式属性，不依赖 <style> —— camo 代理下的 CSP 更宽容。"""
    return (
        f'<text x="{x:g}" y="{y:g}" font-family="{FONT}" font-size="{size:g}" '
        f'font-weight="{weight}" fill="{fill}">{escape(s)}</text>'
    )


def card(repo: dict, blurb: str) -> str:
    name = repo["name"]
    lang = (repo.get("language") or "").strip()
    stars, forks = repo.get("stargazers_count", 0), repo.get("forks_count", 0)
    title_size = 16 if width_of(name, 16) < W - PAD * 2 - 26 else 14

    body = [
        f'<rect x="0.5" y="0.5" rx="8" width="{W - 1}" height="{H - 1}" fill="{BG}" stroke="{BORDER}"/>',
        icon("repo", PAD, 24, ICON),
        txt(PAD + 24, 37, name, title_size, 600, TITLE),
    ]
    for i, line in enumerate(wrap(blurb, 13, W - PAD * 2, LINE_MAX)):
        body.append(txt(PAD, 68 + i * 20, line, 13, 400, TEXT))

    body += [icon("star", PAD, 103, ICON, 15), txt(PAD + 20, 115, str(stars), 12, 400, MUTED)]
    fx = PAD + 20 + width_of(str(stars), 12) + 22
    body += [icon("fork", fx, 103, ICON, 15), txt(fx + 20, 115, str(forks), 12, 400, MUTED)]
    if lang:
        lx = fx + 20 + width_of(str(forks), 12) + 24
        body.append(f'<circle cx="{lx + 6:g}" cy="110" r="6" fill="{LANG_COLORS.get(lang, "#858585")}"/>')
        body.append(txt(lx + 18, 115, lang, 12, 400, MUTED))

    inner = "\n  ".join(body)
    return (
        f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" fill="none" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{escape(name)}">\n  '
        f"{inner}\n</svg>\n"
    )


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    owner, failed = CONFIG["owner"], 0
    for entry in CONFIG["cards"]:
        repo_name = entry["repo"]
        try:
            repo = api(f"/repos/{owner}/{repo_name}")
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            print(f"!! {repo_name}: {exc}", file=sys.stderr)
            failed += 1
            continue
        (OUT_DIR / f"{repo_name}.svg").write_text(card(repo, entry["blurb"]), "utf-8")
        print(f"-> {CONFIG['outDir']}/{repo_name}.svg  ({repo.get('stargazers_count', 0)}* {repo.get('language') or '-'})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
