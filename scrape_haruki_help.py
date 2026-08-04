"""Scrape HarukiBot NEO's public help pages into a command catalog.

The VitePress pages are server-rendered, so no browser or JavaScript runtime
is required. Run this file directly to refresh ``haruki_commands.json``.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html import unescape
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen


DEFAULT_INDEX = "https://neo.haruki.seiunx.com/bot-help/"
DEFAULT_OUTPUT = Path(__file__).with_name("haruki_commands.json")
USER_AGENT = "pjskhelp-command-catalog/1.0"

PAGE_LINK_RE = re.compile(
    r'href=["\'](?P<href>/bot-help/(?:[^"\'#?]+\.html)?)["\']',
    re.IGNORECASE,
)
COMMAND_GROUP_RE = re.compile(
    r"<li>((?:\s*<code\b[^>]*>.*?</code>)+)\s*<ul>",
    re.IGNORECASE | re.DOTALL,
)
CODE_RE = re.compile(r"<code\b[^>]*>(.*?)</code>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
TRAILING_PLACEHOLDER_RE = re.compile(r"\s+<[^>]+>\s*$")

# Toolbox-only command that is described inline instead of in a command list.
EXTRA_COMMANDS = {"/查qid"}


def fetch_text(url: str, timeout: float = 30.0) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def discover_pages(index_url: str, html: str) -> list[str]:
    pages = {urljoin(index_url, match.group("href")) for match in PAGE_LINK_RE.finditer(html)}
    pages.add(index_url)
    return sorted(pages)


def normalize_command(value: str) -> str | None:
    command = unescape(TAG_RE.sub("", value)).strip()
    if not command.startswith("/"):
        return None
    command = TRAILING_PLACEHOLDER_RE.sub("", command).strip()
    return command or None


def extract_commands(html: str) -> list[str]:
    commands: set[str] = set()
    for group in COMMAND_GROUP_RE.finditer(html):
        for code in CODE_RE.finditer(group.group(1)):
            command = normalize_command(code.group(1))
            if command:
                commands.add(command)
    return sorted(commands, key=lambda value: (value.casefold(), value))


def scrape(index_url: str) -> dict:
    index_html = fetch_text(index_url)
    pages: dict[str, list[str]] = {}
    for page_url in discover_pages(index_url, index_html):
        path = urlsplit(page_url).path
        page_key = path.removeprefix("/bot-help/") or "index"
        pages[page_key] = extract_commands(index_html if page_url == index_url else fetch_text(page_url))

    pages.setdefault("toolbox_guide.html", [])
    pages["toolbox_guide.html"] = sorted(
        set(pages["toolbox_guide.html"]) | EXTRA_COMMANDS,
        key=lambda value: (value.casefold(), value),
    )
    all_commands = sorted(
        {command for commands in pages.values() for command in commands},
        key=lambda value: (value.casefold(), value),
    )
    return {
        "source": index_url,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "command_count": len(all_commands),
        "commands": all_commands,
        "pages": pages,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_INDEX, help="Haruki help index URL")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="catalog output path")
    args = parser.parse_args()

    catalog = scrape(args.url)
    args.output.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {catalog['command_count']} commands to {args.output}")


if __name__ == "__main__":
    main()
