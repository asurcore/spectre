#!/usr/bin/env python3
"""Asynchronous OSINT reconnaissance and digital footprint extraction tool."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup

EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
PHONE_RE = re.compile(r"(?:(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{3,4})")
URL_RE = re.compile(r"https?://[^\s'\"<>]+")


class Color:
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


@dataclass(frozen=True)
class Platform:
    name: str
    url_template: str


PLATFORMS = [
    Platform("GitHub", "https://github.com/{username}"),
    Platform("X", "https://x.com/{username}"),
    Platform("Instagram", "https://www.instagram.com/{username}/"),
    Platform("Reddit", "https://www.reddit.com/user/{username}/"),
    Platform("TikTok", "https://www.tiktok.com/@{username}"),
    Platform("Medium", "https://medium.com/@{username}"),
    Platform("Pinterest", "https://www.pinterest.com/{username}/"),
]


def normalize_phone(phone: str) -> str:
    compact = re.sub(r"\s+", " ", phone).strip(" .-")
    digits = re.sub(r"\D", "", compact)
    return compact if len(digits) >= 7 else ""


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    if len(local) <= 2:
        masked_local = "*" * len(local)
    else:
        masked_local = f"{local[0]}{'*' * (len(local) - 2)}{local[-1]}"
    return f"{masked_local}@{domain}"


def redact_result(item: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(item)
    redacted["emails"] = [mask_email(email) for email in item["emails"]]
    redacted.pop("phone_numbers", None)
    redacted["phone_numbers"] = "[REDACTED]"
    return redacted


def extract_artifacts(html: str, page_url: str) -> dict[str, list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_domain = urlparse(page_url).netloc.lower()

    text = soup.get_text(" ", strip=True)
    emails = sorted(set(EMAIL_RE.findall(text)))

    raw_phones = {normalize_phone(match) for match in PHONE_RE.findall(text)}
    phones = sorted(phone for phone in raw_phones if phone)

    links: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith(("mailto:", "tel:", "#", "javascript:")):
            continue
        links.add(urljoin(page_url, href))

    links.update(URL_RE.findall(text))

    external_links: set[str] = set()
    for link in links:
        parsed = urlparse(link)
        if parsed.scheme not in {"http", "https"}:
            continue
        netloc = parsed.netloc.lower()
        if not netloc:
            continue
        if base_domain and (netloc == base_domain or netloc.endswith(f".{base_domain}")):
            continue
        external_links.add(link)

    return {
        "emails": emails,
        "phone_numbers": phones,
        "external_links": sorted(external_links),
    }


async def scan_platform(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    platform: Platform,
    username: str,
) -> dict[str, Any]:
    profile_url = platform.url_template.format(username=username)

    async with semaphore:
        try:
            async with session.get(profile_url, allow_redirects=True) as response:
                status_code = response.status
                html = await response.text(errors="ignore")

                result: dict[str, Any] = {
                    "platform": platform.name,
                    "profile_url": str(response.url),
                    "http_status": status_code,
                    "found": status_code == 200,
                    "error": None,
                    "emails": [],
                    "phone_numbers": [],
                    "external_links": [],
                }

                if status_code == 200:
                    result.update(extract_artifacts(html, str(response.url)))

                return result
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            return {
                "platform": platform.name,
                "profile_url": profile_url,
                "http_status": None,
                "found": False,
                "error": str(exc),
                "emails": [],
                "phone_numbers": [],
                "external_links": [],
            }


async def run_recon(username: str, concurrency: int = 5) -> list[dict[str, Any]]:
    timeout = aiohttp.ClientTimeout(total=15)
    headers = {"User-Agent": "Spectre-OSINT/1.0 (+https://github.com/asurcore/spectre)"}
    semaphore = asyncio.Semaphore(concurrency)

    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        tasks = [scan_platform(session, semaphore, platform, username) for platform in PLATFORMS]
        return await asyncio.gather(*tasks)


def print_report(username: str, results: list[dict[str, Any]]) -> None:
    found_count = sum(1 for item in results if item["found"])
    print(f"\n{Color.BOLD}{Color.CYAN}Spectre OSINT Recon Report{Color.RESET}")
    print(f"{Color.BOLD}Target:{Color.RESET} {username}")
    print(f"{Color.BOLD}Platforms Found:{Color.RESET} {found_count}/{len(results)}\n")

    for item in results:
        safe_item = redact_result(item)
        status_color = Color.GREEN if item["found"] else Color.RED
        status_label = "FOUND" if item["found"] else "NOT FOUND"

        print(f"{Color.BOLD}{safe_item['platform']}{Color.RESET}: {status_color}{status_label}{Color.RESET}")
        print(f"  URL: {safe_item['profile_url']}")
        if safe_item["http_status"] is not None:
            print(f"  HTTP: {safe_item['http_status']}")
        if safe_item["error"]:
            print(f"  Error: {Color.YELLOW}{safe_item['error']}{Color.RESET}")

        print(f"  Emails (masked): {', '.join(safe_item['emails']) if safe_item['emails'] else '-'}")
        print("  Phone Numbers: [REDACTED]")
        print(f"  External Links: {', '.join(safe_item['external_links']) if safe_item['external_links'] else '-'}")
        print()


def export_json(username: str, results: list[dict[str, Any]], output_path: Path | None) -> Path:
    timestamp = datetime.now(tz=timezone.utc)
    safe_results = [redact_result(item) for item in results]
    unique_emails = sorted({email for item in safe_results for email in item["emails"]})
    unique_links = sorted({link for item in results for link in item["external_links"]})

    payload = {
        "target": username,
        "generated_at": timestamp.isoformat(),
        "summary": {
            "total_platforms": len(results),
            "profiles_found": sum(1 for item in results if item["found"]),
            "total_emails": len(unique_emails),
            "total_external_links": len(unique_links),
        },
        "artifacts": {
            "emails": unique_emails,
            "phone_numbers": "[REDACTED]",
            "external_links": unique_links,
        },
        "platform_results": safe_results,
    }

    if output_path is None:
        stamp = timestamp.strftime("%Y%m%dT%H%M%SZ")
        output_path = Path(f"osint_{username}_{stamp}.json")

    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Asynchronous multi-platform OSINT reconnaissance and digital footprint extraction tool.",
    )
    parser.add_argument("username", help="Target username to investigate")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Path to JSON output file (default: osint_<username>_<timestamp>.json)",
    )
    parser.add_argument(
        "-c",
        "--concurrency",
        type=int,
        default=5,
        help="Maximum concurrent requests (default: 5)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.concurrency <= 0:
        raise SystemExit("Concurrency must be a positive integer.")

    results = asyncio.run(run_recon(args.username, concurrency=args.concurrency))
    print_report(args.username, results)
    output_file = export_json(args.username, results, args.output)
    print(f"{Color.BLUE}JSON log exported to {output_file.resolve()}{Color.RESET}")


if __name__ == "__main__":
    main()
