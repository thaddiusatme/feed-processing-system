"""Get InoReader OAuth2 token."""

import os
import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

APP_ID = os.getenv("INOREADER_APP_ID")
APP_KEY = os.getenv("INOREADER_API_KEY")
REDIRECT_URI = "http://localhost:8080/callback"
AUTH_URL = "https://www.inoreader.com/oauth2/auth"
TOKEN_URL = "https://www.inoreader.com/oauth2/token"

# Store the token and state here
auth_code = None
auth_state = None


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code, auth_state
        try:
            # Parse the authorization code from the callback URL
            query_components = parse_qs(urlparse(self.path).query)

            if "state" not in query_components or query_components["state"][0] != auth_state:
                print("\nError: State mismatch!")
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"Authorization failed: Invalid state parameter")
                return

            if "code" in query_components:
                auth_code = query_components["code"][0]
                # Send success response
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"Authorization successful! You can close this window.")
            elif "error" in query_components:
                error = query_components["error"][0]
                error_description = query_components.get("error_description", ["Unknown error"])[0]
                print(f"\nAuthorization Error: {error}")
                print(f"Description: {error_description}")
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(f"Authorization failed: {error_description}".encode())
            else:
                print("\nNo code or error in response")
                print(f"Query parameters: {query_components}")
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"Authorization failed: No code received")
        except Exception as e:
            print(f"\nError in callback: {str(e)}")
            self.send_response(500)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(f"Server error: {str(e)}".encode())

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def get_auth_token():
    global auth_state
    # Generate random state parameter
    auth_state = secrets.token_urlsafe(32)

    # Start local server to receive callback
    server = HTTPServer(("localhost", 8080), CallbackHandler)

    # Construct authorization URL
    auth_params = {
        "client_id": APP_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "read",
        "state": auth_state,
    }
    auth_url = f"{AUTH_URL}?{'&'.join(f'{k}={v}' for k, v in auth_params.items())}"

    print("\n1. Opening browser for authorization...")
    print(f"URL: {auth_url}\n")
    webbrowser.open(auth_url)

    print("2. Waiting for authorization...")
    while auth_code is None:
        server.handle_request()

    print("\n3. Getting access token...")
    # Exchange authorization code for access token
    token_params = {
        "code": auth_code,
        "client_id": APP_ID,
        "client_secret": APP_KEY,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    try:
        response = requests.post(TOKEN_URL, data=token_params)
        print(f"\nToken response status: {response.status_code}")
        print(f"Response body: {response.text}")

        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data["access_token"]

            print("\nSuccess! Here's your access token:")
            print(f"\n{access_token}\n")
            print("Add this token to your .env file as INOREADER_TOKEN")
            return access_token
        else:
            print(f"\nError getting token. Status: {response.status_code}")
            print(f"Error details: {response.text}")
            return None
    except Exception as e:
        print(f"\nException while getting token: {str(e)}")
        return None


if __name__ == "__main__":
    if not APP_ID or not APP_KEY:
        print("Error: INOREADER_APP_ID and INOREADER_API_KEY must be set in .env file")
        exit(1)

    print(f"Using App ID: {APP_ID}")
    get_auth_token()
