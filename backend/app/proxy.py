"""PR11 — resolve the real client address behind a reverse proxy.

Only mounted when BEHIND_PROXY is true. The `hops` setting is the number of
proxies you actually run: X-Forwarded-For is client-controlled on the left and
proxy-controlled on the right, so the trustworthy entry is the Nth from the
end, never the first. Taking the first is the classic mistake — it lets a
client send `X-Forwarded-For: 1.2.3.4` and get a fresh rate-limit bucket per
request.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class ProxyHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, hops: int = 1):
        super().__init__(app)
        self.hops = max(1, hops)

    async def dispatch(self, request: Request, call_next):
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            chain = [p.strip() for p in forwarded.split(",") if p.strip()]
            if len(chain) >= self.hops:
                client_host = chain[-self.hops]
                port = request.scope.get("client", (None, 0))[1] or 0
                request.scope["client"] = (client_host, port)

        proto = request.headers.get("x-forwarded-proto", "")
        if proto:
            # Lets the HSTS header in SecurityHeadersMiddleware fire, since it
            # keys on request.url.scheme == "https".
            request.scope["scheme"] = proto.split(",")[0].strip()

        return await call_next(request)
