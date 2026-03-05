#!/usr/bin/env python3
"""
Tool to inline CSS, JS, and images from a website into a single self-contained HTML file.

Usage:
    python inline_website.py <url> [output_file] [options]

Example:
    python inline_website.py http://example.com/page index.html --minify --no-js

Options:
    --no-css        Skip inlining CSS files
    --no-js         Skip inlining JavaScript files
    --no-images     Skip inlining images
    --minify        Minify HTML output
    --verbose       Show detailed progress
    --max-size      Maximum file size to inline in MB (default: 5)
    --timeout       Timeout for page load in seconds (default: 30)
"""

import argparse
import asyncio
import base64
import re
import sys
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


@dataclass
class Stats:
    """Track statistics about inlining process."""
    css_inlined: int = 0
    js_inlined: int = 0
    images_inlined: int = 0
    css_failed: int = 0
    js_failed: int = 0
    images_failed: int = 0
    original_size: int = 0
    final_size: int = 0
    start_time: float = 0
    end_time: float = 0

    def print_summary(self) -> None:
        """Print summary statistics."""
        duration = self.end_time - self.start_time
        print("\n" + "=" * 60)
        print("📊 Summary Statistics")
        print("=" * 60)
        print(f"✅ CSS files inlined:     {self.css_inlined} ({self.css_failed} failed)")
        print(f"✅ JS files inlined:      {self.js_inlined} ({self.js_failed} failed)")
        print(f"✅ Images inlined:        {self.images_inlined} ({self.images_failed} failed)")
        print(f"📦 Original HTML size:    {self.original_size:,} bytes")
        print(f"📦 Final HTML size:       {self.final_size:,} bytes")
        size_diff = self.final_size - self.original_size
        print(f"📈 Size increase:         {size_diff:,} bytes ({size_diff/self.original_size*100:.1f}%)")
        print(f"⏱️  Total time:            {duration:.2f} seconds")
        print("=" * 60)


@dataclass
class Config:
    """Configuration for inlining process."""
    url: str
    output_file: str = "index.html"
    inline_css: bool = True
    inline_js: bool = True
    inline_images: bool = True
    minify: bool = False
    verbose: bool = False
    max_size_mb: float = 5.0
    timeout: int = 30


class ResourceCache:
    """Cache for fetched resources to avoid duplicate requests."""
    
    def __init__(self):
        self._cache: dict[str, Optional[bytes]] = {}
        self._in_progress: dict[str, asyncio.Future] = {}
    
    async def get(self, url: str, client: httpx.AsyncClient) -> Optional[bytes]:
        """Get resource from cache or fetch if not cached."""
        # Return cached result
        if url in self._cache:
            return self._cache[url]
        
        # If already fetching, wait for it
        if url in self._in_progress:
            return await self._in_progress[url]
        
        # Start new fetch
        future = asyncio.Future()
        self._in_progress[url] = future
        
        try:
            result = await fetch_resource(client, url)
            self._cache[url] = result
            future.set_result(result)
            return result
        except Exception as e:
            future.set_exception(e)
            raise
        finally:
            del self._in_progress[url]


# Global cache instance
_resource_cache = ResourceCache()


def is_local_url(url: str, base_url: str) -> bool:
    """Return True if *url* is relative or shares the same origin as *base_url*."""
    if not url or url.startswith("data:") or url.startswith("#"):
        return False
    parsed = urlparse(url)
    if not parsed.scheme:  # relative path
        return True
    base_parsed = urlparse(base_url)
    return parsed.netloc == base_parsed.netloc


async def fetch_resource(client: httpx.AsyncClient, url: str, max_size_mb: float = 5.0) -> Optional[bytes]:
    """Fetch *url* and return raw bytes, or None on failure."""
    try:
        # Stream response to check size first
        async with client.stream("GET", url, follow_redirects=True, timeout=30.0) as response:
            if response.status_code != 200:
                print(f"  ⚠️  Warning: HTTP {response.status_code} for {url}", file=sys.stderr)
                return None
            
            # Check content length if available
            content_length = response.headers.get("content-length")
            if content_length:
                size_mb = int(content_length) / (1024 * 1024)
                if size_mb > max_size_mb:
                    print(f"  ⚠️  Warning: File too large ({size_mb:.1f}MB > {max_size_mb}MB): {url}", file=sys.stderr)
                    return None
            
            # Read content
            content = await response.aread()
            
            # Check actual size
            size_mb = len(content) / (1024 * 1024)
            if size_mb > max_size_mb:
                print(f"  ⚠️  Warning: File too large ({size_mb:.1f}MB > {max_size_mb}MB): {url}", file=sys.stderr)
                return None
            
            return content
            
    except httpx.TimeoutException:
        print(f"  ⚠️  Warning: Timeout fetching {url}", file=sys.stderr)
        return None
    except Exception as exc:
        print(f"  ⚠️  Warning: Could not fetch {url}: {exc}", file=sys.stderr)
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
    config: Config,
) -> str:
    """Replace url(...) references inside CSS with base64 data URIs when local."""
    pattern = re.compile(r"""url\(\s*(['"]?)([^'"\)]+)\1\s*\)""", re.IGNORECASE)

    results: dict[str, str] = {}

    # Collect all URLs to fetch
    urls_to_fetch = []
    matches = list(pattern.finditer(css_text))
    for m in matches:
        url = m.group(2).strip()
        if is_local_url(url, css_base_url):
            full_url = urljoin(css_base_url, url)
            if full_url not in results:
                urls_to_fetch.append(full_url)

    # Fetch all URLs concurrently
    if urls_to_fetch:
        fetch_tasks = [_resource_cache.get(url, client) for url in urls_to_fetch]
        contents = await asyncio.gather(*fetch_tasks, return_exceptions=True)
        
        for full_url, content in zip(urls_to_fetch, contents):
            if isinstance(content, bytes):
                results[full_url] = to_data_uri(content, full_url)

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
    config: Config,
    stats: Stats,
) -> str:
    """Process *html* by inlining local CSS, JS, and images."""
    soup = BeautifulSoup(html, "html.parser")

    # ── 1. Inline local CSS files ──────────────────────────────────────────────
    if config.inline_css:
        css_links = soup.find_all("link", rel="stylesheet")
        if config.verbose:
            print(f"  Found {len(css_links)} CSS files to inline")
        
        for link in css_links:
            href = link.get("href", "")
            if is_local_url(href, page_url):
                full_url = urljoin(page_url, href)
                if config.verbose:
                    print(f"  🎨 Inlining CSS: {full_url}")
                else:
                    print(f"  Inlining CSS: {full_url}")
                
                content = await _resource_cache.get(full_url, client)
                if content:
                    css_text = content.decode("utf-8", errors="replace")
                    css_text = await inline_css_urls(css_text, full_url, client, config)
                    style_tag = soup.new_tag("style")
                    style_tag.string = css_text
                    link.replace_with(style_tag)
                    stats.css_inlined += 1
                else:
                    stats.css_failed += 1

    # ── 2. Inline local JS files ───────────────────────────────────────────────
    if config.inline_js:
        scripts = soup.find_all("script", src=True)
        if config.verbose:
            print(f"  Found {len(scripts)} JS files to inline")
        
        for script in scripts:
            src = script.get("src", "")
            if is_local_url(src, page_url):
                full_url = urljoin(page_url, src)
                if config.verbose:
                    print(f"  📜 Inlining JS:  {full_url}")
                else:
                    print(f"  Inlining JS:  {full_url}")
                
                content = await _resource_cache.get(full_url, client)
                if content:
                    new_script = soup.new_tag("script")
                    for attr, val in script.attrs.items():
                        if attr != "src":
                            new_script[attr] = val
                    new_script.string = content.decode("utf-8", errors="replace")
                    script.replace_with(new_script)
                    stats.js_inlined += 1
                else:
                    stats.js_failed += 1

    # ── 3. Convert local <img src> to base64 data URIs ────────────────────────
    if config.inline_images:
        images = soup.find_all("img", src=True)
        if config.verbose:
            print(f"  Found {len(images)} images to inline")
        
        # Collect all image URLs (including srcset)
        image_urls = []
        for img in images:
            src = img.get("src", "")
            if is_local_url(src, page_url):
                image_urls.append((img, "src", urljoin(page_url, src)))
            
            # Handle srcset
            srcset = img.get("srcset", "")
            if srcset:
                for srcset_item in srcset.split(","):
                    parts = srcset_item.strip().split()
                    if parts:
                        src_url = parts[0]
                        if is_local_url(src_url, page_url):
                            image_urls.append((img, "srcset", urljoin(page_url, src_url)))
        
        # Process images
        for img, attr_type, full_url in image_urls:
            if config.verbose:
                print(f"  🖼️  Encoding img: {full_url}")
            else:
                print(f"  Encoding img: {full_url}")
            
            content = await _resource_cache.get(full_url, client)
            if content:
                data_uri = to_data_uri(content, full_url)
                
                if attr_type == "src":
                    img["src"] = data_uri
                    stats.images_inlined += 1
                elif attr_type == "srcset":
                    # Replace in srcset
                    srcset = img.get("srcset", "")
                    old_url = full_url.replace(urljoin(page_url, ""), "")
                    img["srcset"] = srcset.replace(old_url, data_uri)
            else:
                stats.images_failed += 1
    
    # ── 4. Handle inline styles with background-image ─────────────────────────
    if config.inline_images:
        elements_with_style = soup.find_all(style=True)
        if config.verbose and elements_with_style:
            print(f"  Found {len(elements_with_style)} elements with inline styles")
        
        bg_pattern = re.compile(r"""background(?:-image)?\s*:\s*url\(\s*(['"]?)([^'"\)]+)\1\s*\)""", re.IGNORECASE)
        
        for element in elements_with_style:
            style = element.get("style", "")
            matches = list(bg_pattern.finditer(style))
            
            if matches:
                for match in matches:
                    url = match.group(2).strip()
                    if is_local_url(url, page_url):
                        full_url = urljoin(page_url, url)
                        content = await _resource_cache.get(full_url, client)
                        if content:
                            data_uri = to_data_uri(content, full_url)
                            style = style.replace(match.group(0), f"background-image: url({data_uri})")
                
                element["style"] = style

    return str(soup)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inline CSS, JS, and images from a website into a single HTML file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://example.com
  %(prog)s https://example.com output.html --minify
  %(prog)s https://example.com --no-js --verbose
  %(prog)s https://example.com --max-size 10
        """
    )
    
    parser.add_argument("url", help="Website URL to process")
    parser.add_argument("output", nargs="?", default="index.html", 
                       help="Output file path (default: index.html)")
    parser.add_argument("--no-css", action="store_true", 
                       help="Skip inlining CSS files")
    parser.add_argument("--no-js", action="store_true", 
                       help="Skip inlining JavaScript files")
    parser.add_argument("--no-images", action="store_true", 
                       help="Skip inlining images")
    parser.add_argument("--minify", action="store_true", 
                       help="Minify HTML output (basic)")
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help="Show detailed progress")
    parser.add_argument("--max-size", type=float, default=5.0, metavar="MB",
                       help="Maximum file size to inline in MB (default: 5)")
    parser.add_argument("--timeout", type=int, default=30, metavar="SECONDS",
                       help="Timeout for page load in seconds (default: 30)")
    
    args = parser.parse_args()
    
    # Create configuration
    config = Config(
        url=args.url,
        output_file=args.output,
        inline_css=not args.no_css,
        inline_js=not args.no_js,
        inline_images=not args.no_images,
        minify=args.minify,
        verbose=args.verbose,
        max_size_mb=args.max_size,
        timeout=args.timeout,
    )
    
    # Create stats tracker
    stats = Stats()
    stats.start_time = time.time()
    
    print(f"🌐 Loading {config.url} ...")
    
    # Load page with Playwright
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(config.url, wait_until="networkidle", timeout=config.timeout * 1000)
        except Exception as e:
            print(f"❌ Error loading page: {e}", file=sys.stderr)
            await browser.close()
            sys.exit(1)

        html = await page.content()
        page_url = page.url
        stats.original_size = len(html.encode("utf-8"))

        await browser.close()

    print("⚙️  Processing HTML ...")
    if config.verbose:
        print(f"  Original size: {stats.original_size:,} bytes")
    
    # Process HTML with httpx client
    async with httpx.AsyncClient() as client:
        processed_html = await process_html(html, page_url, client, config, stats)
    
    # Optional minification
    if config.minify:
        print("🗜️  Minifying HTML...")
        # Basic minification - remove extra whitespace
        processed_html = re.sub(r'\s+', ' ', processed_html)
        processed_html = re.sub(r'>\s+<', '><', processed_html)
    
    stats.final_size = len(processed_html.encode("utf-8"))
    
    # Write output
    with open(config.output_file, "w", encoding="utf-8") as fh:
        fh.write(processed_html)

    stats.end_time = time.time()
    
    print(f"✅ Saved to {config.output_file}")
    
    # Print statistics
    if config.verbose or stats.css_inlined > 0 or stats.js_inlined > 0 or stats.images_inlined > 0:
        stats.print_summary()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
