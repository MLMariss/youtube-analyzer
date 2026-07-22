#!/usr/bin/env python3
"""
ONE-TIME SETUP. Run on your own machine to mint a refresh token.

The refresh token is what lets the GitHub Actions collector authenticate with
no browser and no human. You run this once; the workflow then uses the result
indefinitely (provided the OAuth app is Published rather than in Testing mode,
where refresh tokens expire after 7 days).

    python scripts/mint_token.py --client-id XXX --client-secret YYY

No third-party packages required; standard library only.

--- Which OAuth client type? -------------------------------------------------
Either works:

  Desktop app  (recommended, simplest)
      No redirect URI registration needed at all. Loopback redirects are
      explicitly and permanently supported for this client type.
      Console > Credentials > Create Credentials > OAuth client ID > Desktop app

  Web application  (reuse the one the browser dashboard already uses)
      You must add this EXACT redirect URI to the client first:
          http://localhost:8765/
      Plain http is normally rejected, but localhost is exempt from the
      HTTPS requirement, and Google's own web-server docs use
      http://localhost:PORT for this purpose.
      Console > Credentials > your client > Authorized redirect URIs > Add

Note this is separate from "Authorized JavaScript origins", which is what the
browser dashboard used. Adding a redirect URI does not affect those.

--- Prerequisites ------------------------------------------------------------
  1. Enable BOTH "YouTube Analytics API" and "YouTube Reporting API"
     under APIs & Services > Library.
  2. Strongly recommended: Google Auth Platform > Audience > Publish app.
     In Testing mode the collector breaks every 7 days.

You will see an "unverified app" warning during consent. Click
Advanced > Go to ... (unsafe). That is expected for a private single-user app.
"""

import argparse
import http.server
import json
import secrets
import socketserver
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request

try:
    from auth import SCOPES, TOKEN_URL, USER_AGENT
except ImportError:  # allow running from repo root as well as scripts/
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    from auth import SCOPES, TOKEN_URL, USER_AGENT

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
DEFAULT_PORT = 8765

_result = {}
_done = threading.Event()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _result.update({k: v[0] for k, v in params.items()})
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        if "code" in params:
            msg = ("<h2>Authorised.</h2>"
                   "<p>You can close this tab and return to the terminal.</p>")
        else:
            msg = ("<h2>Authorisation failed.</h2><pre>"
                   + urllib.parse.urlparse(self.path).query + "</pre>")
        self.wfile.write(msg.encode())
        _done.set()

    def log_message(self, *args):
        pass  # keep console output clean


def main():
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
    )
    ap.add_argument("--client-id", required=True)
    ap.add_argument("--client-secret", required=True)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT,
                    help=f"loopback port (default {DEFAULT_PORT}); if you change "
                         "it and use a Web client, register the matching URI")
    args = ap.parse_args()

    redirect_uri = f"http://localhost:{args.port}/"
    state = secrets.token_urlsafe(16)

    auth_params = {
        "client_id": args.client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",   # required to receive a refresh token
        "prompt": "consent",        # force a refresh token even on re-auth
        "state": state,
    }
    url = AUTH_URL + "?" + urllib.parse.urlencode(auth_params)

    socketserver.TCPServer.allow_reuse_address = True
    try:
        httpd = socketserver.TCPServer(("localhost", args.port), Handler)
    except OSError as e:
        sys.exit(f"Could not bind localhost:{args.port} ({e}). "
                 f"Close whatever is using it, or pass --port.")

    threading.Thread(target=httpd.handle_request, daemon=True).start()

    print("Redirect URI in use:", redirect_uri)
    print("(Web application clients must have this registered; Desktop app "
          "clients need nothing.)\n")
    print("Open this URL to consent:\n")
    print(url + "\n")
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:
        pass

    print("Waiting for the redirect (5 min timeout)...")
    if not _done.wait(timeout=300):
        httpd.server_close()
        sys.exit("Timed out waiting for authorisation.")
    httpd.server_close()

    if "code" not in _result:
        err = _result.get("error", "(none)")
        msg = f"No authorisation code received. Google returned: {err}"
        if err == "redirect_uri_mismatch":
            msg += (f"\n\nAdd {redirect_uri} to your OAuth client's "
                    "Authorized redirect URIs, or create a Desktop app client "
                    "instead. Changes can take a few minutes to apply.")
        sys.exit(msg)

    if _result.get("state") != state:
        sys.exit("State mismatch; aborting for safety.")

    body = urllib.parse.urlencode({
        "code": _result["code"],
        "client_id": args.client_id,
        "client_secret": args.client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }).encode()

    req = urllib.request.Request(TOKEN_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", USER_AGENT)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        sys.exit("Error exchanging code: " + e.read().decode(errors="replace"))

    refresh = payload.get("refresh_token")
    if not refresh:
        print(json.dumps(payload, indent=2), file=sys.stderr)
        sys.exit(
            "No refresh_token in the response. Revoke prior access at "
            "myaccount.google.com/permissions and run this again "
            "(Google only issues a refresh token on first consent unless "
            "prompt=consent forces it)."
        )

    bar = "=" * 70
    print("\n" + bar)
    print("SUCCESS - add these three as GitHub repository secrets")
    print(bar)
    print(f"YT_CLIENT_ID      = {args.client_id}")
    print(f"YT_CLIENT_SECRET  = {args.client_secret}")
    print(f"YT_REFRESH_TOKEN  = {refresh}")
    print(bar)
    print("\nRepo > Settings > Secrets and variables > Actions > New repository secret")
    print("Never commit these values to the repository.")


if __name__ == "__main__":
    main()
