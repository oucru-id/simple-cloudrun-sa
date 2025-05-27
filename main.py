from flask import Flask, jsonify
from google.auth import default
from google.auth.transport.requests import Request
import os
import requests

app = Flask(__name__)

@app.route('/', methods=['GET'])
def get_service_account_info():
    try:
        # For Cloud Run, you might not need to specify scopes at all
        # The service account permissions are managed through IAM roles
        credentials, project_id = default()
        
        # On Cloud Run, the most reliable way to get the service account email
        # is through the metadata server
        try:
            response = requests.get(
                'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email',
                headers={'Metadata-Flavor': 'Google'},
                timeout=2
            )
            service_account_email = response.text.strip()
        except Exception as e:
            # Fallback to credential property
            service_account_email = getattr(credentials, 'service_account_email', f"default (error: {str(e)})")
        
        # Request an access token - no need to specify scope for Cloud Run
        # The token will have the scopes assigned to the service account
        request = Request()
        credentials.refresh(request)
        token = credentials.token
        
        # Return all information in one response
        return jsonify({
            "service_account": service_account_email,
            "project_id": project_id,
            "token": token,
            "success": True
        })
    except Exception as e:
        return jsonify({
            "service_account": "Unknown",
            "project_id": "Unknown",
            "token": "Error retrieving token",
            "error": str(e),
            "success": False
        }), 500

if __name__ == '__main__':
    # Get port from environment variable or default to 8080
    port = int(os.environ.get('PORT', 8080))
    # Run the app, listening on all interfaces
    app.run(host='0.0.0.0', port=port)