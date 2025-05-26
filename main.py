from flask import Flask, jsonify
from google.auth import default
from google.auth.transport.requests import Request
import os

app = Flask(__name__)

@app.route('/', methods=['GET'])
def get_service_account_info():
    try:
        # Get credentials from the environment
        credentials, project_id = default(scopes=['https://www.googleapis.com/auth/cloud-healthcare'])
        
        # Get service account email
        service_account_email = credentials.service_account_email
        
        # Request an access token
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
