# Module 8 — Security and robustness

**Goal:** reason about the attack surface of a system that fetches user-supplied URLs and
talks to LLMs, and understand the defence-in-depth in the ingestion path.

**From embedded to here:** you already validate every byte at a **trust boundary** (untrusted
input from a bus/radio/user) before acting on it. Same discipline here: a URL or a model
output is untrusted input. The new twist is **SSRF** — the *server itself* can be tricked into
making requests to places it shouldn't.

## Concepts

### 1. The trust boundaries in this system
- **User URL → server fetch** (the big one): SSRF, oversized/slow responses, unsafe content.
- **Web search results / fetched pages → LLM context**: untrusted text entering a prompt
  (prompt-injection awareness).
- **Secrets**: API keys must never be logged or committed.
- **Inbound exposure** (if you add WhatsApp/web hooks): anyone reaching the endpoint can spend
  your compute — hence allowlists.

### 2. SSRF, concretely
If your server fetches `http://169.254.169.254/...` (cloud metadata) or `http://127.0.0.1:5432`
(your own Postgres) because a user pasted that URL, it can leak credentials or hit internal
services. The fix is to **resolve the host and refuse non-public IPs**.

### 3. The defences in [src/rag/url_ingest.py](../../src/rag/url_ingest.py)
- **Scheme allowlist** — only `http`/`https` (blocks `file://`, `data:`, `gopher://`).
- **No credentials in URL** (`user:pass@host` rejected).
- **DNS-resolve + public-IP check** — `_is_public_ip` refuses loopback/private/link-local
  (incl. `169.254.169.254`)/multicast/reserved, checking **every** resolved address.
- **Manual redirect following** — re-validates the host on **every hop** (a redirect to an
  internal address is the classic bypass).
- **Timeouts + streamed size cap** — bounded resource use (DoS protection).
- **Content-Type allowlist** — text/HTML/plain only; HTML is parsed to text with scripts
  removed and **never executed**.
- **Optional host allowlist** (`URL_INGEST_ALLOW_HOSTS`) — closes SSRF entirely for locked-down
  deployments.

### 4. Defence in depth, not one check
No single control is sufficient — schemes, IPs, redirects, size, and content type each block a
different attack. This layered approach is the same philosophy as multiple independent safety
interlocks.

### 5. Honest residual risk
DNS **rebinding** (host resolves public at validation, then re-resolves internal at connect)
isn't fully closed without pinning the validated IP onto the socket. The code documents this
and offers the host allowlist as the hard mitigation. *Knowing and stating your residual risk
is part of the job.*

### 6. Secrets hygiene
Keys live in `.env` (gitignored) or session-only UI state; `.env.example` carries no real
values. Never log message bodies or tokens.

## Hands-on lab

1. **Prove the SSRF blocks** (no network needed — validation fails first):
   ```python
   from src.rag import url_ingest as u
   for bad in ["file:///etc/passwd","http://127.0.0.1:5432","http://169.254.169.254/latest/meta-data/",
               "http://10.0.0.5","https://user:pass@example.com","ftp://example.com"]:
       try: u.validate_url(bad); print("NOT BLOCKED:", bad)
       except u.URLSecurityError as e: print("blocked:", bad, "->", str(e)[:40])
   u.validate_url("https://example.com")  # should NOT raise
   print("public host allowed")
   ```
2. **Test the size cap:** set `URL_INGEST_MAX_BYTES=1000` in `.env`, then ingest a large page
   via the sidebar and confirm it's rejected with a clear error. Restore the value.
3. **Lock it down:** set `URL_INGEST_ALLOW_HOSTS=example.com`, confirm any other host is
   refused, then clear it.
4. **Threat-model an extension:** in 5 bullet points, list what you'd add before exposing an
   inbound webhook (see Module 8 of the WhatsApp design note if present): signature
   verification, sender allowlist, rate limiting, idempotency, no secrets in logs.

## Checkpoint 8

**Concept check**
1. What is SSRF and which specific address would you most want to block, and why?
2. Why must redirects be validated on *every* hop, not just the first URL?
3. Why is checking *all* resolved IPs (not just the first) important?
4. What is DNS rebinding and what's the practical mitigation here?

<details><summary>Answers</summary>

1. Server-Side Request Forgery: tricking the server into making requests on the attacker's
   behalf. `169.254.169.254` (cloud metadata) is the highest-value target — it can expose
   instance credentials.
2. A safe initial URL can 3xx-redirect to an internal address; without per-hop validation the
   redirect bypasses the check.
3. A host can resolve to multiple addresses; if any is private, the request could reach an
   internal service, so all must be public.
4. The host resolves to a public IP during validation, then to a private IP at connect time.
   Full mitigation needs IP pinning on the socket; the practical mitigation here is the
   `URL_INGEST_ALLOW_HOSTS` allowlist.
</details>

**Practical task (pass criterion):** all six malicious URLs are blocked and
`https://example.com` validates; you demonstrated the size cap and the host allowlist, then
restored `.env`. ✅
