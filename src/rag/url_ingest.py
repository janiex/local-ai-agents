"""Securely fetch a URL and ingest its text into the knowledge base.

Threat model: the URL is user-supplied and therefore untrusted. The main risks
when a server fetches an arbitrary URL are SSRF (reaching internal/cloud-metadata
services), oversized/slow responses (DoS), and unsafe content handling. Defences
applied here:

  * scheme allowlist (http/https only) — blocks file://, gopher://, data:, etc.
  * no embedded credentials (user:pass@host)
  * DNS resolution + IP validation — every resolved address must be public;
    private / loopback / link-local (incl. 169.254.169.254 metadata) / reserved
    ranges are rejected
  * redirects followed manually, re-validating the target host on every hop
  * connect/read timeouts and a hard response-size cap (streamed)
  * Content-Type allowlist (text/HTML/plain only)
  * HTML is parsed to plain text and scripts/styles are dropped — content is
    only ever stored as text, never rendered or executed

Residual risk: DNS rebinding between validation and connect is not fully
eliminated (would require pinning the validated IP on the socket); private-range
blocking covers the primary SSRF vector. Use URL_INGEST_ALLOW_HOSTS to restrict
to a trusted set of hosts when stronger guarantees are needed.
"""
from __future__ import annotations

import ipaddress
import socket
from typing import Any, Dict, Tuple
from urllib.parse import urljoin, urlparse

import requests

from ..config import settings

ALLOWED_SCHEMES = ("http", "https")
ALLOWED_CONTENT_TYPES = ("text/html", "application/xhtml+xml", "text/plain", "text/markdown")
USER_AGENT = "ToniSheriff-RAG/1.0 (+url-ingest)"


class URLSecurityError(Exception):
    """Raised when a URL fails a security check."""


def _allowed_hosts() -> set:
    raw = settings.url_ingest_allow_hosts or ""
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def _is_public_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_url(url: str) -> None:
    """Raise URLSecurityError unless the URL is safe to fetch."""
    parsed = urlparse(url)

    if parsed.scheme not in ALLOWED_SCHEMES:
        raise URLSecurityError(f"Only http/https URLs are allowed (got {parsed.scheme!r}).")
    if parsed.username or parsed.password:
        raise URLSecurityError("URLs with embedded credentials are not allowed.")
    host = parsed.hostname
    if not host:
        raise URLSecurityError("URL has no host.")

    allow = _allowed_hosts()
    if allow and host.lower() not in allow:
        raise URLSecurityError(f"Host {host!r} is not in URL_INGEST_ALLOW_HOSTS.")

    # Resolve and validate every address the host maps to.
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise URLSecurityError(f"Could not resolve host {host!r}: {e}")

    addrs = {info[4][0] for info in infos}
    if not addrs:
        raise URLSecurityError(f"Host {host!r} did not resolve to any address.")
    for ip in addrs:
        if not _is_public_ip(ip):
            raise URLSecurityError(
                f"Refusing to fetch {host!r}: resolves to non-public address {ip}."
            )


def fetch_url(url: str) -> Tuple[str, str, str]:
    """Return (content_type, text, final_url) after security checks.

    Follows redirects manually, re-validating each hop.
    """
    max_bytes = settings.url_ingest_max_bytes
    timeout = settings.url_ingest_timeout
    current = url

    for _ in range(settings.url_ingest_max_redirects + 1):
        validate_url(current)
        resp = requests.get(
            current,
            stream=True,
            allow_redirects=False,  # we follow manually + re-validate each hop
            timeout=(timeout, timeout),
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain;q=0.9"},
        )
        try:
            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("Location")
                if not location:
                    raise URLSecurityError("Redirect without a Location header.")
                current = urljoin(current, location)
                continue  # validated at the top of the loop

            if resp.status_code != 200:
                raise URLSecurityError(f"Unexpected HTTP status {resp.status_code}.")

            content_type = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if content_type not in ALLOWED_CONTENT_TYPES:
                raise URLSecurityError(
                    f"Unsupported Content-Type {content_type or 'unknown'!r} "
                    f"(allowed: {', '.join(ALLOWED_CONTENT_TYPES)})."
                )

            # Reject early if the server advertises an oversized body.
            clen = resp.headers.get("Content-Length")
            if clen and clen.isdigit() and int(clen) > max_bytes:
                raise URLSecurityError(f"Response too large ({clen} bytes > {max_bytes}).")

            # Stream with a hard cap regardless of advertised length.
            chunks, total = [], 0
            for chunk in resp.iter_content(8192):
                total += len(chunk)
                if total > max_bytes:
                    raise URLSecurityError(f"Response exceeded size limit ({max_bytes} bytes).")
                chunks.append(chunk)
            body = b"".join(chunks)
            text = body.decode(resp.encoding or "utf-8", errors="replace")
            return content_type, text, current
        finally:
            resp.close()

    raise URLSecurityError("Too many redirects.")


def _html_to_text(html: str) -> Tuple[str, str]:
    """Return (title, text) from HTML, dropping scripts/styles. Never executes."""
    try:
        import lxml.html

        doc = lxml.html.fromstring(html)
        for bad in doc.xpath("//script | //style | //noscript | //template | //head"):
            bad.getparent().remove(bad) if bad.getparent() is not None else None
        title = ""
        titles = lxml.html.fromstring(html).xpath("//title/text()")
        if titles:
            title = titles[0].strip()
        text = doc.text_content()
    except Exception:
        # Fallback: crude tag strip (still text-only, never executed).
        import re

        text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        title = ""

    # Collapse whitespace.
    lines = [ln.strip() for ln in text.splitlines()]
    text = "\n".join(ln for ln in lines if ln)
    return title, text


def ingest_url(kb, url: str) -> Dict[str, Any]:
    """Fetch a URL securely and add its text to the knowledge base."""
    if not settings.url_ingest_enabled:
        raise URLSecurityError("URL ingestion is disabled (URL_INGEST_ENABLED=false).")

    url = (url or "").strip()
    if not url:
        raise URLSecurityError("No URL provided.")
    if "://" not in url:
        url = "https://" + url  # default to https, then validated normally

    content_type, raw, final_url = fetch_url(url)

    if content_type in ("text/html", "application/xhtml+xml"):
        title, text = _html_to_text(raw)
    else:
        title, text = "", raw.strip()

    if not text.strip():
        raise URLSecurityError("No extractable text content at that URL.")

    result = kb.add_document(
        text,
        metadata={"type": "url", "source": final_url, "title": title or final_url},
    )
    result.update({"title": title or final_url, "url": final_url, "chars": len(text)})
    return result
