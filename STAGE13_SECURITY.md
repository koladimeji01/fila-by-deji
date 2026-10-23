# Stage 1 — Client-aware login throttling behind Render

FÌLÀ's production backend is served behind Render and Cloudflare. A raw TCP peer
address can be the same internal proxy for many visitors, causing an unrelated
customer's login attempts to consume another customer's rate limit.

The rate limiter now derives its anonymous Redis key from `CF-Connecting-IP`
**only** when `APP_ENV=production` and `RATE_LIMIT_TRUST_RENDER_CLIENT_IP=true`.
Cloudflare sets this single-IP header at its edge. Do not enable this flag for
a deployment that is not protected by Cloudflare at the ingress.
We deliberately continue launching Uvicorn with `--no-proxy-headers`.
Raw `X-Forwarded-For` chains are never trusted for identity, and malformed,
private, or absent client-IP headers fall back to the socket peer. Only
SHA-256 hashes of the resulting client address are used in Redis keys.

## Verify

1. CI tests: `python -m pytest -q` from `backend/`.
2. Render automatically redeploys the backend on `main`. Check the deploy
   status is Live and the public `/api/v1/health` and `/api/v1/products`.
3. Send normal customer login requests from two separate public connections.
   A temporary 10-per-5-minute per-IP login limit should be independent,
   assuming Cloudflare supplies a trusted CF-Connecting-IP. Do not test by
   repeatedly guessing passwords on real accounts.
4. No database, stock, customer records or UI pages are modified.

If requests consistently lack `CF-Connecting-IP`, investigate the Render
ingress configuration before trying any other forwarded header; do not set
`FORWARDED_ALLOW_IPS=*` or read the leftmost X-Forwarded-For value.
