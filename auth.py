"""
OAuth for the unattended collector.

The browser dashboard could only ever hold a ~1 hour access token, because a
browser cannot safely keep a client secret. A server-side flow can, and that is
what allows this collector to run with nobody signed in.

Credentials come from environment variables (GitHub Actions secrets in CI):
    YT_CLIENT_ID
    YT_CLIENT_SECRET
    YT_REFRESH_TOKEN

Mint the refresh token once via scripts/mint_token.py.

IMPORTANT: while the OAuth app's publishing status is "Testing", refresh tokens
expire after 7 days and the collector will begin failing with invalid_grant.
Publish the app (Google Auth Platform > Audience > Publish app) so they persist.
Self-consenting to your own unverified app is fine for a single-user tool.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

TOKEN_URL = "https://oauth2.googleapis.com/token"

# yt-analytics.readonly covers BOTH the Analytics API and the Reporting API.
# youtube.readonly is needed to read video titles/metadata via the Data API.
# The monetary scope is deliberately excluded: Google's docs state it grants no
# monetary data for channel reports, so it would add a sensitive scope for nothing.
SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
]

USER_AGENT = "mlmariss-youtube-analyzer/1.0"


class AuthError(RuntimeError):
    pass


class Credentials:
    """Holds a refresh token and mints short-lived access tokens on demand."""

    def __init__(self, client_id, client_secret, refresh_token):
        missing = [
            name for name, val in (
                ("YT_CLIENT_ID", client_id),
                ("YT_CLIENT_SECRET", client_secret),
                ("YT_REFRESH_TOKEN", refresh_token),
            ) if not val
        ]
        if missing:
            raise AuthError(
                "Missing OAuth credentials: " + ", ".join(missing) + ".\n"
                "Set them as environment variables locally, or as repository "
                "secrets under Settings > Secrets and variables > Actions.\n"
                "Mint a refresh token with: python scripts/mint_token.py"
            )
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self._access_token = None
        self._expires_at = 0.0

    @classmethod
    def from_env(cls):
        return cls(
            os.environ.get("YT_CLIENT_ID", "").strip(),
            os.environ.get("YT_CLIENT_SECRET", "").strip(),
            os.environ.get("YT_REFRESH_TOKEN", "").strip(),
        )

    def access_token(self):
        # Refresh a minute early so a token cannot expire mid-request.
        if self._access_token and time.time() < self._expires_at - 60:
            return self._access_token

        body = urllib.parse.urlencode({
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }).encode()

        req = urllib.request.Request(TOKEN_URL, data=body, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("User-Agent", USER_AGENT)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            if "invalid_grant" in detail:
                raise AuthError(
                    "Refresh token rejected (invalid_grant). Likely causes:\n"
                    "  1. The OAuth app is still in Testing mode, where refresh "
                    "tokens expire after 7 days. Publish the app to fix this "
                    "permanently.\n"
                    "  2. Access was revoked at myaccount.google.com/permissions.\n"
                    "  3. The token was minted against a different client ID.\n"
                    "Re-run scripts/mint_token.py to issue a new one.\n"
                    f"Raw response: {detail}"
                ) from e
            raise AuthError(f"Token refresh failed (HTTP {e.code}): {detail}") from e

        self._access_token = payload["access_token"]
        self._expires_at = time.time() + int(payload.get("expires_in", 3600))
        return self._access_token

    def headers(self, extra=None):
        h = {
            "Authorization": "Bearer " + self.access_token(),
            "User-Agent": USER_AGENT,
        }
        if extra:
            h.update(extra)
        return h
