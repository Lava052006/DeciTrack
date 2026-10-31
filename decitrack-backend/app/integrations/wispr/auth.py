
import asyncio
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Event, Thread
from urllib.parse import parse_qs, urlparse

from mcp.client.auth import (
    AuthorizationCodeResult,
    OAuthClientProvider,
    TokenStorage,
)
from mcp.shared.auth import (
    OAuthClientInformationFull,
    OAuthClientMetadata,
    OAuthToken,
)


class InMemoryTokenStorage(TokenStorage):
    """Temporary token storage for the initial connection test."""

    def __init__(self):
        self.tokens: OAuthToken | None = None
        self.client_info: OAuthClientInformationFull | None = None

    async def get_tokens(self):
        return self.tokens

    async def set_tokens(self, tokens: OAuthToken):
        self.tokens = tokens

    async def get_client_info(self):
        return self.client_info

    async def set_client_info(self, client_info: OAuthClientInformationFull):
        self.client_info = client_info


class LocalOAuthCallback:
    """Receives the OAuth redirect from the browser."""

    def __init__(self, port: int = 3030):
        self.event = Event()
        self.data = {}

        callback_data = self.data
        callback_event = self.event

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlparse(self.path)

                if parsed.path != "/callback":
                    self.send_error(404)
                    return

                params = parse_qs(parsed.query)

                if "error" in params:
                    callback_data["error"] = params["error"][0]
                    callback_data["error_description"] = params.get(
                        "error_description", [""]
                    )[0]
                elif "code" in params:
                    callback_data["code"] = params["code"][0]
                    callback_data["state"] = params.get("state", [None])[0]
                    callback_data["iss"] = params.get("iss", [None])[0]
                else:
                    self.send_error(400)
                    return

                callback_event.set()

                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h2>Authorization response received."
                    b" You can close this window.</h2></body></html>"
                )

            def log_message(self, format, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", port), Handler)
        self.thread = Thread(
            target=self.server.serve_forever,
            daemon=True,
        )

    @property
    def redirect_uri(self):
        return "http://127.0.0.1:3030/callback"

    def start(self):
        self.thread.start()

    async def wait_for_callback(self):
        received = await asyncio.to_thread(self.event.wait, 300)

        if not received:
            raise TimeoutError("Timed out waiting for Wispr authorization.")

        if self.data.get("error"):
            raise RuntimeError(
                "OAuth authorization failed: "
                + self.data.get("error")
                + " "
                + self.data.get("error_description", "")
            )

        if not self.data.get("code"):
            raise RuntimeError("OAuth callback did not contain an authorization code.")

        return AuthorizationCodeResult(
            code=self.data["code"],
            state=self.data.get("state"),
            iss=self.data.get("iss"),
        )

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


def create_wispr_oauth():
    callback = LocalOAuthCallback()
    callback.start()

    metadata = OAuthClientMetadata.model_validate({
        "client_name": "DeciTrack",
        "redirect_uris": [callback.redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
    })

    async def redirect_handler(authorization_url: str):
        print("\nOpening Wispr authorization in your browser...")
        opened = webbrowser.open(authorization_url)

        if not opened:
            print("Open this authorization URL manually:")
            print(authorization_url)

    async def callback_handler():
        try:
            return await callback.wait_for_callback()
        finally:
            callback.stop()

    oauth_provider = OAuthClientProvider(
        server_url="https://api.wisprflow.ai/connect/mcp",
        client_metadata=metadata,
        storage=InMemoryTokenStorage(),
        redirect_handler=redirect_handler,
        callback_handler=callback_handler,
    )

    return oauth_provider, callback
   