"""Simple OAuth consent and login UI for Hydra.

This minimal Flask app handles the login and consent flows required by Hydra.
In production, you'd want proper user authentication, session management, etc.
"""

import os
import sys
from urllib.parse import urlencode

import requests
from flask import Flask, redirect, render_template_string, request

app = Flask(__name__)
HYDRA_ADMIN_URL = os.getenv("HYDRA_ADMIN_URL", "http://localhost:4445")

# User authentication - format: "username:password,username2:password2"
ALLOWED_USERS = {}
users_str = os.getenv("ALLOWED_USERS", "")
if users_str:
    for user_pair in users_str.split(","):
        if ":" in user_pair:
            username, password = user_pair.split(":", 1)
            ALLOWED_USERS[username.strip()] = password.strip()


# Simple login template
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Mealie MCP Login</title>
    <style>
        body { font-family: system-ui; max-width: 400px; margin: 100px auto; padding: 20px; }
        input { width: 100%; padding: 10px; margin: 10px 0; }
        button { width: 100%; padding: 12px; background: #2563eb; color: white; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #1d4ed8; }
        .error { color: #dc2626; margin: 10px 0; }
    </style>
</head>
<body>
    <h2>🍽️ Mealie MCP Login</h2>
    <p>Sign in to authorize Claude to access your Mealie recipes</p>
    {% if error %}
    <div class="error">{{ error }}</div>
    {% endif %}
    <form method="post">
        <input type="text" name="username" placeholder="Username" required>
        <input type="password" name="password" placeholder="Password" required>
        <input type="hidden" name="login_challenge" value="{{ login_challenge }}">
        <button type="submit">Sign In</button>
    </form>
</body>
</html>
"""

# Simple consent template
CONSENT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Authorize Access</title>
    <style>
        body { font-family: system-ui; max-width: 500px; margin: 100px auto; padding: 20px; }
        .app { background: #f3f4f6; padding: 15px; border-radius: 8px; margin: 20px 0; }
        .scopes { margin: 20px 0; }
        .scope { background: white; padding: 10px; margin: 5px 0; border-radius: 4px; }
        button { padding: 12px 24px; margin: 5px; border: none; border-radius: 4px; cursor: pointer; }
        .allow { background: #16a34a; color: white; }
        .deny { background: #dc2626; color: white; }
        button:hover { opacity: 0.9; }
    </style>
</head>
<body>
    <h2>🔐 Authorize Application</h2>
    <div class="app">
        <strong>{{ client_name }}</strong> wants to access your Mealie MCP Server
    </div>
    
    <div class="scopes">
        <p><strong>Requested permissions:</strong></p>
        {% for scope in scopes %}
        <div class="scope">✓ {{ scope }}</div>
        {% endfor %}
    </div>
    
    <p>This will allow the application to:</p>
    <ul>
        <li>Search and view your recipes</li>
        <li>Manage meal plans</li>
        <li>Access shopping lists</li>
    </ul>
    
    <form method="post" style="margin-top: 30px;" id="consentForm">
        <input type="hidden" name="consent_challenge" value="{{ consent_challenge }}">
        <input type="hidden" name="action" id="actionInput" value="">
        <button type="button" class="allow" id="allowBtn" onclick="submitConsent('allow')">Allow Access</button>
        <button type="button" class="deny" id="denyBtn" onclick="submitConsent('deny')">Deny</button>
    </form>
    
    <script>
        function submitConsent(action) {
            document.getElementById('actionInput').value = action;
            document.getElementById('allowBtn').disabled = true;
            document.getElementById('denyBtn').disabled = true;
            document.getElementById('consentForm').submit();
        }
    </script>
</body>
</html>
"""


@app.route("/login", methods=["GET", "POST"])
def login():
    """Handle login flow."""
    login_challenge = request.args.get("login_challenge") or request.form.get("login_challenge")
    
    if not login_challenge:
        return "Missing login_challenge", 400
    
    if request.method == "GET":
        # Show login form
        return render_template_string(LOGIN_TEMPLATE, login_challenge=login_challenge, error=None)
    
    # Process login
    username = request.form.get("username")
    password = request.form.get("password")
    
    # Validate credentials
    if not username or not password:
        return render_template_string(
            LOGIN_TEMPLATE,
            login_challenge=login_challenge,
            error="Username and password required"
        )
    
    # Check against allowed users
    if not ALLOWED_USERS:
        return render_template_string(
            LOGIN_TEMPLATE,
            login_challenge=login_challenge,
            error="No users configured. Set ALLOWED_USERS environment variable."
        )
    
    if username not in ALLOWED_USERS or ALLOWED_USERS[username] != password:
        return render_template_string(
            LOGIN_TEMPLATE,
            login_challenge=login_challenge,
            error="Invalid username or password"
        )
    
    # Accept the login challenge
    try:
        response = requests.put(
            f"{HYDRA_ADMIN_URL}/admin/oauth2/auth/requests/login/accept",
            params={"login_challenge": login_challenge},
            json={
                "subject": username,  # User identifier
                "remember": True,
                "remember_for": 3600,
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        
        # Redirect to Hydra's redirect URL
        return redirect(data["redirect_to"])
    
    except Exception as e:
        return f"Error accepting login: {e}", 500


@app.route("/consent", methods=["GET", "POST"])
def consent():
    """Handle consent flow."""
    consent_challenge = request.args.get("consent_challenge") or request.form.get("consent_challenge")
    
    if not consent_challenge:
        return "Missing consent_challenge", 400
    
    # Get consent request info
    try:
        response = requests.get(
            f"{HYDRA_ADMIN_URL}/admin/oauth2/auth/requests/consent",
            params={"consent_challenge": consent_challenge},
            timeout=10,
        )
        response.raise_for_status()
        consent_request = response.json()
    except Exception as e:
        return f"Error fetching consent request: {e}", 500
    
    if request.method == "GET":
        # Show consent form
        return render_template_string(
            CONSENT_TEMPLATE,
            consent_challenge=consent_challenge,
            client_name=consent_request.get("client", {}).get("client_name", "Unknown App"),
            scopes=consent_request.get("requested_scope", []),
        )
    
    # Process consent
    action = request.form.get("action")
    print(f"DEBUG: Consent form data: {dict(request.form)}", file=sys.stderr, flush=True)
    print(f"DEBUG: action = {action!r}", file=sys.stderr, flush=True)
    
    if action == "allow":
        # Accept consent
        try:
            response = requests.put(
                f"{HYDRA_ADMIN_URL}/admin/oauth2/auth/requests/consent/accept",
                params={"consent_challenge": consent_challenge},
                json={
                    "grant_scope": consent_request.get("requested_scope", []),
                    "grant_access_token_audience": consent_request.get("requested_access_token_audience", []),
                    "remember": True,
                    "remember_for": 3600,
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            return redirect(data["redirect_to"])
        except Exception as e:
            return f"Error accepting consent: {e}", 500
    
    else:
        # Reject consent
        try:
            response = requests.put(
                f"{HYDRA_ADMIN_URL}/admin/oauth2/auth/requests/consent/reject",
                params={"consent_challenge": consent_challenge},
                json={
                    "error": "access_denied",
                    "error_description": "User denied consent",
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            return redirect(data["redirect_to"])
        except Exception as e:
            return f"Error rejecting consent: {e}", 500


@app.route("/error")
def error():
    """Error page."""
    error_msg = request.args.get("error", "Unknown error")
    error_desc = request.args.get("error_description", "")
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>Error</title></head>
    <body style="font-family: system-ui; max-width: 500px; margin: 100px auto; padding: 20px;">
        <h2>⚠️ Authorization Error</h2>
        <p><strong>{error_msg}</strong></p>
        <p>{error_desc}</p>
    </body>
    </html>
    """


@app.route("/logout")
def logout():
    """Logout page."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Logged Out</title></head>
    <body style="font-family: system-ui; max-width: 500px; margin: 100px auto; padding: 20px;">
        <h2>✅ Logged Out</h2>
        <p>You have been successfully logged out.</p>
    </body>
    </html>
    """


if __name__ == "__main__":
    print("Starting Hydra Consent UI on http://localhost:3000")
    app.run(host="0.0.0.0", port=3000, debug=True)
