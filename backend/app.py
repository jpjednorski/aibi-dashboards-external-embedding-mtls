"""
Flask Backend for AI/BI External Embedding
Handles user authentication, OAuth token minting, and dashboard embedding context.
"""

import os
import time
import json
import base64
import urllib.parse
import re
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import requests

# Load environment variables from .env file
load_dotenv('.env')

app = Flask(__name__)
app.config['DEBUG'] = True  # Development mode

# Enable CORS for frontend communication (allow https://localhost:443 for mTLS flow)
CORS(app, supports_credentials=False, origins=['http://localhost:3000', 'https://localhost:443'])

# Demo users showing row-level security
# Different departments will see different dashboard data
DUMMY_USERS = {
    'sales': {
        'id': 'user_sales',
        'name': 'Sales Team TV',
        'email': 'sales-tv@example.com',
        'department': 'AUTOMOBILE'
    },
    'machinery': {
        'id': 'user_machinery',
        'name': 'Machinery Team TV',
        'email': 'machinery-tv@example.com',
        'department': 'MACHINERY'
    },
    'furniture': {
        'id': 'user_furniture',
        'name': 'Furniture Team TV',
        'email': 'furniture-tv@example.com',
        'department': 'FURNITURE'
    }
}


def _load_json_map(env_var_name):
    """Load a JSON object from an environment variable."""
    raw = os.environ.get(env_var_name)
    if not raw:
        return None, None
    try:
        return json.loads(raw), None
    except json.JSONDecodeError as exc:
        return None, f"Invalid JSON in {env_var_name}: {exc}"


def _get_user_from_mtls_headers(headers):
    """
    Resolve user context from mTLS verification headers set by a reverse proxy.
    Requires mTLS verification to be successful.
    """
    verify_status = headers.get('X-Client-Verify')
    if verify_status != 'SUCCESS':
        return None, "Client certificate verification failed"

    subject_dn = headers.get('X-Client-Subject-Dn')
    cert_sha256 = headers.get('X-Client-Cert-Sha256')
    cert_fingerprint = headers.get('X-Client-Cert-Fingerprint')

    subject_map, subject_err = _load_json_map('MTLS_SUBJECT_TO_USER_JSON')
    if subject_err:
        return None, subject_err

    sha_map, sha_err = _load_json_map('MTLS_SHA256_TO_USER_JSON')
    if sha_err:
        return None, sha_err

    fingerprint_map, fingerprint_err = _load_json_map('MTLS_FINGERPRINT_TO_USER_JSON')
    if fingerprint_err:
        return None, fingerprint_err

    def normalize_subject_dn(value):
        if not value:
            return value
        normalized = value.strip()
        if normalized.startswith('/'):
            normalized = normalized.lstrip('/').replace('/', ',')
        normalized = re.sub(r'\s*=\s*', '=', normalized)
        normalized = re.sub(r',\s*', ',', normalized)
        return normalized

    user = None
    if subject_dn and subject_map:
        normalized_subject_dn = normalize_subject_dn(subject_dn)
        user = subject_map.get(subject_dn) or subject_map.get(normalized_subject_dn)
    if not user and cert_sha256 and sha_map:
        user = sha_map.get(cert_sha256)
    if not user and cert_fingerprint and fingerprint_map:
        user = fingerprint_map.get(cert_fingerprint)

    if not user:
        normalized_subject_dn = normalize_subject_dn(subject_dn) if subject_dn else None
        if subject_dn:
            return None, (
                "No user mapping for client certificate. "
                f"Subject DN: {subject_dn} "
                f"(normalized: {normalized_subject_dn})"
            )
        return None, "No user mapping for client certificate"

    required_fields = {'id', 'name', 'email', 'department'}
    missing_fields = required_fields - set(user.keys())
    if missing_fields:
        return None, f"User mapping missing fields: {', '.join(sorted(missing_fields))}"

    return user, None


def mint_databricks_token(user_data):
    """
    Mint an OAuth token for Databricks dashboard embedding.
    
    Follows the official Databricks 3-step token generation process:
    1. Get all-apis token from OIDC endpoint
    2. Get token info for the dashboard with external viewer context
    3. Generate scoped token with authorization details
    
    This enables row-level security by passing external_viewer_id (user identity)
    and external_value (user attributes like department) to Databricks.
    
    Args:
        user_data: Dictionary containing user information
        
    Returns:
        Dictionary with token and expiration info
        
    Raises:
        Exception: If required credentials are missing or token generation fails
    """
    
    # Databricks workspace configuration
    workspace_url = os.environ.get('DATABRICKS_WORKSPACE_URL')
    client_id = os.environ.get('DATABRICKS_CLIENT_ID')
    client_secret = os.environ.get('DATABRICKS_CLIENT_SECRET')
    dashboard_id = os.environ.get('DATABRICKS_DASHBOARD_ID')
    
    # Validate required configuration
    if not all([workspace_url, client_id, client_secret, dashboard_id]):
        raise Exception(
            "Missing required Databricks configuration. "
            "Please check your .env file has all required values: "
            "DATABRICKS_WORKSPACE_URL, DATABRICKS_CLIENT_ID, "
            "DATABRICKS_CLIENT_SECRET, DATABRICKS_DASHBOARD_ID"
        )
    
    # Create Basic Auth header
    basic_auth = base64.b64encode(
        f"{client_id}:{client_secret}".encode()
    ).decode()
    
    # Step 1: Get all-apis token
    oidc_response = requests.post(
        f"{workspace_url}/oidc/v1/token",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {basic_auth}",
        },
        data=urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "scope": "all-apis"
        })
    )
    
    if oidc_response.status_code != 200:
        raise Exception(f"Failed to get OIDC token: {oidc_response.status_code} - {oidc_response.text}")
    print(f"oidc_response.status_code: {oidc_response.status_code}")
    oidc_token = oidc_response.json()["access_token"]
    
    # Step 2: Get token info for the dashboard with user context
    # external_viewer_id: unique user identifier for row-level security
    # external_value: user attributes (e.g., department) for filtering
    token_info_url = (
        f"{workspace_url}/api/2.0/lakeview/dashboards/"
        f"{dashboard_id}/published/tokeninfo"
        f"?external_viewer_id={urllib.parse.quote(user_data['email'])}"
        f"&external_value={urllib.parse.quote(user_data['department'])}"
    )
    print(f"Token info URL: {token_info_url}")
    token_info_response = requests.get(
        token_info_url,
        headers={"Authorization": f"Bearer {oidc_token}"}
    )
    
    if token_info_response.status_code != 200:
        raise Exception(f"Failed to get token info: {token_info_response.status_code} - {token_info_response.text}")
    
    token_info = token_info_response.json()
    print(f"Token info response: {json.dumps(token_info, indent=2)}")
    
    # Step 3: Generate scoped token with authorization details
    params = token_info.copy()
    authorization_details = params.pop("authorization_details", None)
    print(f"Authorization details: {json.dumps(authorization_details, indent=2)}")
    params.update({
        "grant_type": "client_credentials",
        "authorization_details": json.dumps(authorization_details)
    })
    
    scoped_response = requests.post(
        f"{workspace_url}/oidc/v1/token",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {basic_auth}",
        },
        data=urllib.parse.urlencode(params)
    )
    
    if scoped_response.status_code != 200:
        raise Exception(f"Failed to get scoped token: {scoped_response.status_code} - {scoped_response.text}")
    
    scoped_token_data = scoped_response.json()
    
    return {
        'access_token': scoped_token_data['access_token'],
        'token_type': 'Bearer',
        'expires_in': scoped_token_data.get('expires_in', 3600),
        'created_at': int(time.time())
    }


@app.route('/api/dashboard/embed-config', methods=['GET'])
def get_embed_config():
    """
    Provide dashboard embedding configuration and token.
    
    This endpoint:
    1. Verifies mTLS client certificate (via proxy headers from nginx)
    2. Maps client identity to a user context
    3. Mints a fresh Databricks OAuth token for that user
    4. Returns dashboard configuration and token to frontend
    
    The frontend will use this information to initialize the
    Databricks embedding SDK.
    """
    
    # Verify mTLS headers from nginx
    user, error = _get_user_from_mtls_headers(request.headers)
    if error:
        print(f"❌ mTLS verification failed: {error}")
        return jsonify({'error': error}), 401

    print(f"✅ Authenticated as: {user['name']} ({user['email']})")

    try:
        # Mint fresh token for the current user
        token_data = mint_databricks_token(user)
        print(f"✅ Token minted successfully for {user['email']}")
    except Exception as e:
        error_message = str(e)
        print(f"❌ Token minting failed: {error_message}")
        return jsonify({'error': error_message}), 500
    
    # Dashboard configuration
    dashboard_config = {
        'workspace_url': os.environ.get('DATABRICKS_WORKSPACE_URL'),
        'workspace_id': os.environ.get('DATABRICKS_WORKSPACE_ID'),
        'dashboard_id': os.environ.get('DATABRICKS_DASHBOARD_ID'),
        'warehouse_id': os.environ.get('DATABRICKS_WAREHOUSE_ID'),
        'embed_token': token_data['access_token'],
        'token_expires_in': token_data['expires_in'],
        'user_context': {
            'id': user['id'],
            'name': user['name'],
            'email': user['email'],
            'department': user['department']
        }
    }
    
    return jsonify(dashboard_config)


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
    })


if __name__ == '__main__':
    # Run Flask development server with auto-reload
    # Changes to app.py will automatically restart the server
    # In production, use a production WSGI server like Gunicorn
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=True,
        use_debugger=True
    )


