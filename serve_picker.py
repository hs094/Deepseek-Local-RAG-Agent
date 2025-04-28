#!/usr/bin/env python3
"""
Simple HTTP server to serve the Google Drive Picker HTML file.
This helps avoid CORS issues when using file:// URLs.
"""

import http.server
import socketserver
import os
import webbrowser
import argparse
import json
import tempfile
from urllib.parse import quote, parse_qs
from http import HTTPStatus

# Default port
PORT = 8000

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_POST(self):
        """Handle POST requests for file selection."""
        if self.path == '/handle_files':
            # Get the content length
            content_length = int(self.headers['Content-Length'])
            # Read the POST data
            post_data = self.rfile.read(content_length).decode('utf-8')
            # Parse the form data
            form_data = parse_qs(post_data)

            if 'files' in form_data:
                # Get the files JSON
                files_json = form_data['files'][0]

                try:
                    # Parse the JSON
                    files = json.loads(files_json)

                    # Save the files to a temporary file
                    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
                        json.dump(files, f)
                        temp_file = f.name

                    print(f"Selected files saved to {temp_file}")
                    print(f"Selected {len(files)} files: {', '.join(f['name'] for f in files)}")

                    # Send a success response
                    self.send_response(HTTPStatus.OK)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()

                    # Send a response that will close the window
                    response = """
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Files Received</title>
                        <style>
                            body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }
                            .success { color: green; font-weight: bold; }
                        </style>
                    </head>
                    <body>
                        <h1 class="success">Files Selected Successfully!</h1>
                        <p>You can close this window and return to the Streamlit app.</p>
                        <p>Click the "Process Selected Files" button in Streamlit to continue.</p>
                        <script>
                            // Close the window after a short delay
                            setTimeout(() => {
                                window.close();
                            }, 3000);
                        </script>
                    </body>
                    </html>
                    """
                    self.wfile.write(response.encode())
                except Exception as e:
                    # Send an error response
                    self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
                    self.send_header('Content-type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(f"Error processing files: {str(e)}".encode())
                    print(f"Error processing files: {str(e)}")
            else:
                # Send a bad request response
                self.send_response(HTTPStatus.BAD_REQUEST)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b"No files received")
        else:
            # Handle other POST requests
            super().do_POST()

def run_server(port=PORT, host=""):
    """Run the HTTP server on the specified port and host.

    Args:
        port: Port number to listen on
        host: Host address to bind to. Empty string means all interfaces.
    """
    handler = CustomHandler

    # Try to find an available port
    for attempt in range(10):
        try:
            with socketserver.TCPServer((host, port), handler) as httpd:
                hostname = "0.0.0.0" if host == "" else host
                print(f"Serving at http://{hostname}:{port}")
                print(f"Press Ctrl+C to stop the server")
                httpd.serve_forever()
                break
        except OSError:
            print(f"Port {port} is in use, trying {port + 1}...")
            port += 1
    else:
        print(f"Could not find an available port after 10 attempts")
        return

def open_picker(token, api_key, app_id, port=PORT):
    """Open the Google Drive Picker in a browser."""
    # URL encode the parameters
    token_encoded = quote(token)
    api_key_encoded = quote(api_key)
    app_id_encoded = quote(app_id)

    print(api_key_encoded)
    print(app_id_encoded)

    # Construct the URL
    url = f"http://localhost:{port}/google_drive_popup.html?token={token_encoded}&apiKey={api_key_encoded}&appId={app_id_encoded}"

    # Open the URL in a browser
    webbrowser.open(url)
    print(f"Opening Google Drive Picker at {url}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Serve Google Drive Picker HTML and open in browser")
    parser.add_argument("--token", help="OAuth token")
    parser.add_argument("--api-key", help="Google API key")
    parser.add_argument("--app-id", help="Google App ID")
    parser.add_argument("--port", type=int, default=PORT, help=f"Port to serve on (default: {PORT})")
    parser.add_argument("--host", default="", help="Host address to bind to (default: all interfaces)")
    parser.add_argument("--serve-only", action="store_true", help="Only serve the HTML file without opening the browser")

    args = parser.parse_args()

    if not args.serve_only and (not args.token or not args.api_key or not args.app_id):
        print("Error: token, api-key, and app-id are required unless --serve-only is specified")
        parser.print_help()
        exit(1)

    if not args.serve_only:
        # Open the picker in a browser
        open_picker(args.token, args.api_key, args.app_id, args.port)

    # Run the server
    run_server(port=args.port, host=args.host)
