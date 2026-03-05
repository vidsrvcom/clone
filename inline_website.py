#!/usr/bin/env python3
"""
Tool to inline CSS, JS, and images from a website into a single self-contained HTML file.

Usage:
    python inline_website.py <url> [output_file]

Example:
    python inline_website.py http://example.com/page index.html
"""

import asyncio
import base64
import re
import sys
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


def is_local_url(url: str, base_url: str) -> bool:
    """Return True if *url* is relative or shares the same origin as *base_url*."""
    if not url or url.startswith("data:") or url.startswith("#"):
        return False
    parsed = urlparse(url)
    if not parsed.scheme:  # relative path
        return True
    base_parsed = urlparse(base_url)
    return parsed.netloc == base_parsed.netloc


async def fetch_resource(client: httpx.AsyncClient, url: str) -> bytes | None:
    """Fetch *url* and return raw bytes, or None on failure."""
    try:
        response = await client.get(url, follow_redirects=True, timeout=30.0)
        if response.status_code == 200:
            return response.content
        print(f"  Warning: HTTP {response.status_code} for {url}", file=sys.stderr)
        return None
    except Exception as exc:
        print(f"  Warning: Could not fetch {url}: {exc}", file=sys.stderr)
        return None


def mime_for_url(url: str) -> str:
    """Guess MIME type from the URL path extension."""
    ext = urlparse(url).path.rsplit(".", 1)[-1].lower()
    return {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "svg": "image/svg+xml",
        "ico": "image/x-icon",
        "webp": "image/webp",
        "bmp": "image/bmp",
        "ttf": "font/truetype",
        "otf": "font/otf",
        "woff": "font/woff",
        "woff2": "font/woff2",
        "eot": "application/vnd.ms-fontobject",
        "js": "application/javascript",
        "css": "text/css",
    }.get(ext, "application/octet-stream")


def to_data_uri(content: bytes, url: str) -> str:
    """Encode *content* as a base64 data URI."""
    mime = mime_for_url(url)
    b64 = base64.b64encode(content).decode("ascii")
    return f"data:{mime};base64,{b64}"


async def inline_css_urls(
    css_text: str,
    css_base_url: str,
    client: httpx.AsyncClient,
) -> str:
    """Replace url(...) references inside CSS with base64 data URIs when local."""
    pattern = re.compile(r"""url\(\s*(['"]?)([^'"\)]+)\1\s*\)""", re.IGNORECASE)

    results: dict[str, str] = {}

    matches = list(pattern.finditer(css_text))
    for m in matches:
        url = m.group(2).strip()
        if is_local_url(url, css_base_url):
            full_url = urljoin(css_base_url, url)
            if full_url not in results:
                content = await fetch_resource(client, full_url)
                if content:
                    results[full_url] = to_data_uri(content, url)

    def replacer(m: re.Match) -> str:
        url = m.group(2).strip()
        if is_local_url(url, css_base_url):
            full_url = urljoin(css_base_url, url)
            if full_url in results:
                return f"url({results[full_url]})"
        return m.group(0)

    return pattern.sub(replacer, css_text)


async def process_html(
    html: str,
    page_url: str,
    client: httpx.AsyncClient,
) -> str:
    """Process *html* by inlining local CSS, JS, and images."""
    soup = BeautifulSoup(html, "html.parser")

    # ── 1. Inline local CSS files ──────────────────────────────────────────────
    for link in soup.find_all("link", rel="stylesheet"):
        href = link.get("href", "")
        if is_local_url(href, page_url):
            full_url = urljoin(page_url, href)
            print(f"  Inlining CSS: {full_url}")
            content = await fetch_resource(client, full_url)
            if content:
                css_text = content.decode("utf-8", errors="replace")
                css_text = await inline_css_urls(css_text, full_url, client)
                style_tag = soup.new_tag("style")
                style_tag.string = css_text
                link.replace_with(style_tag)

    # ── 2. Inline local JS files ───────────────────────────────────────────────
    for script in soup.find_all("script", src=True):
        src = script.get("src", "")
        if is_local_url(src, page_url):
            full_url = urljoin(page_url, src)
            print(f"  Inlining JS:  {full_url}")
            content = await fetch_resource(client, full_url)
            if content:
                new_script = soup.new_tag("script")
                for attr, val in script.attrs.items():
                    if attr != "src":
                        new_script[attr] = val
                new_script.string = content.decode("utf-8", errors="replace")
                script.replace_with(new_script)

    # ── 3. Convert local <img src> to base64 data URIs ────────────────────────
    for img in soup.find_all("img", src=True):
        src = img.get("src", "")
        if is_local_url(src, page_url):
            full_url = urljoin(page_url, src)
            print(f"  Encoding img: {full_url}")
            content = await fetch_resource(client, full_url)
            if content:
                img["src"] = to_data_uri(content, src)

    return str(soup)


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python inline_website.py <url> [output_file]")
        print("  url         - The website URL to process")
        print("  output_file - Path to save the result (default: index.html)")
        sys.exit(1)

    url = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "index.html"

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page()

        print(f"Loading {url} ...")
        await page.goto(url, wait_until="networkidle")

        html = await page.content()
        page_url = page.url

        await browser.close()

    print("Processing HTML ...")
    async with httpx.AsyncClient() as client:
        processed_html = await process_html(html, page_url, client)

    with open(output_file, "w", encoding="utf-8") as fh:
        fh.write(processed_html)

    print(f"Saved to {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
