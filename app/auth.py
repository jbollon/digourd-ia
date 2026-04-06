"""
Google OAuth middleware — attivato solo se REQUIRE_AUTH=true.

Env vars richieste quando attivo:
  GOOGLE_CLIENT_ID      → OAuth 2.0 Client ID
  GOOGLE_CLIENT_SECRET  → OAuth 2.0 Client Secret
  ALLOWED_EMAIL         → es. tuoemail@gmail.com
  SESSION_SECRET        → stringa random lunga (es. openssl rand -hex 32)
"""

import os
from authlib.integrations.starlette_client import OAuth
from starlette.requests import Request
from starlette.responses import RedirectResponse, HTMLResponse

REQUIRE_AUTH   = os.getenv("REQUIRE_AUTH", "false").lower() == "true"
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-me-in-production")

oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email"},
)

PUBLIC_PATHS = {"/auth/login", "/auth/callback", "/static", "/favicon.ico"}


def is_public(path: str) -> bool:
    return any(path == p or path.startswith(p) for p in PUBLIC_PATHS)


async def auth_middleware(request: Request, call_next):
    """Middleware: protegge tutte le route se REQUIRE_AUTH=true."""
    if not REQUIRE_AUTH or is_public(request.url.path):
        return await call_next(request)

    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/auth/login")

    return await call_next(request)


def add_auth_routes(app):
    """Aggiunge /auth/login e /auth/callback all'app FastAPI."""

    @app.get("/auth/login")
    async def login(request: Request):
        redirect_uri = str(request.url_for("auth_callback"))
        return await oauth.google.authorize_redirect(request, redirect_uri)

    @app.get("/auth/callback", name="auth_callback")
    async def auth_callback(request: Request):
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get("userinfo")
        if not user_info:
            return HTMLResponse("Autenticazione fallita.", status_code=400)

        email = user_info.get("email", "")
        request.session["user"] = {"email": email, "name": user_info.get("name")}
        return RedirectResponse(url="/")

    @app.get("/auth/logout")
    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse(url="/")
