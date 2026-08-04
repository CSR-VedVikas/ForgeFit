from slowapi import Limiter
from slowapi.util import get_remote_address

# PR11 — get_remote_address reads request.client.host. Behind nginx that is the
# proxy for every request, which would collapse all users into one bucket and
# make the 10/minute auth limit useless. ProxyHeadersMiddleware (app/proxy.py,
# mounted only when BEHIND_PROXY=true) rewrites scope["client"] from the
# trusted position in X-Forwarded-For before this runs, so no change is needed
# here — but verify with /api/health behind the proxy before relying on it.
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
