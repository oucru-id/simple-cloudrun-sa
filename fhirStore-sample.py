import os
import json
import requests
from flask import Flask, request, jsonify
from google.cloud import secretmanager
from google.oauth2 import service_account
from google.auth.transport.requests import Request

app = Flask(__name__)

# --- Configuration from Environment Variables ---
PROJECT_ID = os.environ.get("PROJECT_ID")
FHIR_LOCATION = os.environ.get("FHIR_LOCATION", "us-central1")
FHIR_DATASET_ID = os.environ.get("FHIR_DATASET_ID")
FHIR_STORE_ID = os.environ.get("FHIR_STORE_ID")
CR_SA_CREDENTIALS_ID = os.environ.get("CR_SA_CREDENTIALS_ID")

# Check for required environment variables
required_env_vars = {
    "PROJECT_ID": PROJECT_ID,
    "FHIR_DATASET_ID": FHIR_DATASET_ID,
    "FHIR_STORE_ID": FHIR_STORE_ID,
    "CR_SA_CREDENTIALS_ID": CR_SA_CREDENTIALS_ID
}

missing_vars = [name for name, value in required_env_vars.items() if not value]
if missing_vars:
    print(f"ERROR: Missing environment variables: {', '.join(missing_vars)}")

# Base URL for the FHIR store
FHIR_STORE_URL = f"https://healthcare.googleapis.com/v1/projects/{PROJECT_ID}/locations/{FHIR_LOCATION}/datasets/{FHIR_DATASET_ID}/fhirStores/{FHIR_STORE_ID}/fhir"

def access_secret(secret_id, version_id="latest"):
    """Access the secret from Secret Manager."""
    if not PROJECT_ID:
        print("ERROR: PROJECT_ID environment variable is not set")
        return None
        
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/{version_id}"
    try:
        response = client.access_secret_version(request={"name": name})
        payload = response.payload.data.decode('UTF-8')
        print(f"Successfully accessed secret: {secret_id}")
        return payload
    except Exception as e:
        print(f"Error accessing secret '{secret_id}': {e}")
        return None

def get_credentials():
    """Get Google Cloud credentials from the service account key in Secret Manager."""
    try:
        if not CR_SA_CREDENTIALS_ID:
            print("ERROR: CR_SA_CREDENTIALS_ID environment variable not set.")
            return None

        credentials_json_str = access_secret(CR_SA_CREDENTIALS_ID)
        if not credentials_json_str:
            return None
            
        credentials_info = json.loads(credentials_json_str)
        credentials = service_account.Credentials.from_service_account_info(
            credentials_info,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        
        return credentials
    except Exception as e:
        print(f"Error getting credentials: {e}")
        return None

def get_auth_token():
    """Get an OAuth 2.0 access token using service account credentials from Secret Manager"""
    try:
        credentials = get_credentials()
        if not credentials:
            return None
            
        credentials.refresh(Request())
        return credentials.token
    except Exception as e:
        print(f"Error getting access token: {e}")
        return None

def check_config():
    """Check if all required configuration is available"""
    if missing_vars:
        return False, f"Missing configuration: {', '.join(missing_vars)}"
    return True, None

def make_fhir_request(method, path, data=None, params=None):
    """Helper function to make FHIR API requests"""
    # Get an authentication token
    token = get_auth_token()
    if not token:
        return None, "Failed to obtain authentication token", 500
    
    # Set up the request headers
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/fhir+json",
        "Accept": "application/fhir+json"
    }
    
    url = f"{FHIR_STORE_URL}/{path}"
    
    # Make the request to the FHIR store
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, params=params)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=data)
        elif method.upper() == "PUT":
            response = requests.put(url, headers=headers, json=data)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers)
        else:
            return None, f"Unsupported method: {method}", 400
        
        # Check if the request was successful
        response.raise_for_status()
        
        # Return the response
        if response.content:
            return response.json(), None, response.status_code
        return {}, None, response.status_code
        
    except requests.exceptions.HTTPError as e:
        # Handle HTTP errors
        error_message = f"HTTP Error: {e.response.status_code}"
        try:
            error_details = e.response.json()
            return error_details, error_message, e.response.status_code
        except:
            return None, f"{error_message} - {e.response.text}", e.response.status_code
            
    except Exception as e:
        # Handle other errors
        return None, f"Request failed: {str(e)}", 500

@app.route('/patient', methods=['POST'])
def create_patient():
    """
    Create a new FHIR Patient resource
    
    Example request body:
    {
        "resourceType": "Patient",
        "name": [
            {
                "use": "official",
                "family": "Smith",
                "given": ["John"]
            }
        ],
        "gender": "male",
        "birthDate": "1970-01-01"
    }
    """
    # Check configuration
    config_ok, error_msg = check_config()
    if not config_ok:
        return jsonify({"error": error_msg}), 500
        
    # Get the patient data from the request
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
        
    patient_data = request.get_json()
    
    # Ensure the resourceType is Patient
    if not patient_data or patient_data.get("resourceType") != "Patient":
        return jsonify({
            "error": "Invalid request body. Must contain a Patient resource."
        }), 400
    
    # Make the request to create the patient
    response_data, error, status_code = make_fhir_request("POST", "Patient", data=patient_data)
    
    if error:
        return jsonify({"error": error, "details": response_data}), status_code
        
    return jsonify(response_data), status_code

@app.route('/patient/<patient_id>', methods=['GET'])
def get_patient(patient_id):
    """Retrieve a FHIR Patient resource by ID"""
    # Check configuration
    config_ok, error_msg = check_config()
    if not config_ok:
        return jsonify({"error": error_msg}), 500
    
    # Make the request to get the patient
    response_data, error, status_code = make_fhir_request("GET", f"Patient/{patient_id}")
    
    if error:
        if status_code == 404:
            return jsonify({"error": f"Patient with ID {patient_id} not found"}), 404
        return jsonify({"error": error, "details": response_data}), status_code
        
    return jsonify(response_data), status_code

@app.route('/patient/<patient_id>', methods=['PUT'])
def update_patient(patient_id):
    """
    Update an existing FHIR Patient resource
    
    Example request body:
    {
        "resourceType": "Patient",
        "id": "patient-id",
        "name": [
            {
                "use": "official",
                "family": "Smith",
                "given": ["John", "Updated"]
            }
        ],
        "gender": "male",
        "birthDate": "1970-01-01"
    }
    """
    # Check configuration
    config_ok, error_msg = check_config()
    if not config_ok:
        return jsonify({"error": error_msg}), 500
        
    # Get the patient data from the request
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
        
    patient_data = request.get_json()
    
    # Ensure the resourceType is Patient
    if not patient_data or patient_data.get("resourceType") != "Patient":
        return jsonify({
            "error": "Invalid request body. Must contain a Patient resource."
        }), 400
    
    # Ensure the ID in the body matches the ID in the URL
    if "id" in patient_data and patient_data["id"] != patient_id:
        return jsonify({
            "error": f"ID in body ('{patient_data['id']}') does not match ID in URL ('{patient_id}')."
        }), 400
    
    # Set the ID in the patient data to match the URL
    patient_data["id"] = patient_id
    
    # Make the request to update the patient
    response_data, error, status_code = make_fhir_request("PUT", f"Patient/{patient_id}", data=patient_data)
    
    if error:
        return jsonify({"error": error, "details": response_data}), status_code
        
    return jsonify(response_data), status_code

@app.route('/patient/<patient_id>', methods=['DELETE'])
def delete_patient(patient_id):
    """Delete a FHIR Patient resource by ID"""
    # Check configuration
    config_ok, error_msg = check_config()
    if not config_ok:
        return jsonify({"error": error_msg}), 500
    
    # Make the request to delete the patient
    response_data, error, status_code = make_fhir_request("DELETE", f"Patient/{patient_id}")
    
    if error:
        return jsonify({"error": error, "details": response_data}), status_code
    
    # Return a 204 No Content response for successful deletion
    if status_code == 204 or (status_code == 200 and not response_data):
        return '', 204
        
    return jsonify(response_data), status_code

@app.route('/patient', methods=['GET'])
def search_patients():
    """
    Search for FHIR Patient resources with filters
    
    Example query parameters:
    - name=John
    - family=Smith
    - given=John
    - gender=male
    - birthdate=1970-01-01
    - _count=10 (limit results)
    - _sort=family (sort by family name)
    """
    # Check configuration
    config_ok, error_msg = check_config()
    if not config_ok:
        return jsonify({"error": error_msg}), 500
    
    # Get query parameters
    query_params = request.args.to_dict(flat=False)
    
    # Make the request to search for patients
    response_data, error, status_code = make_fhir_request("GET", "Patient", params=query_params)
    
    if error:
        return jsonify({"error": error, "details": response_data}), status_code
        
    return jsonify(response_data), status_code

@app.route('/', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    if missing_vars:
        return jsonify({
            "status": "unhealthy", 
            "message": "FHIR API is misconfigured. Missing environment variables.",
            "missing": missing_vars
        }), 503
    return jsonify({
        "status": "healthy", 
        "message": "FHIR API is running."
    }), 200

if __name__ == '__main__':
    PORT = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=PORT, debug=False)
