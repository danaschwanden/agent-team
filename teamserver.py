import json
import os.path

from fastmcp import FastMCP

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/contacts']

mcp = FastMCP("My MCP Team Server")

service = None

@mcp.tool()
def greet(name: str) -> str:
    return f"Hello, {name}!"

def get_credentials():
    """Retrieves valid credentials."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)  # Ensure credentials.json is present
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def get_people_service():
    """Builds and returns the Google People API service object."""
    #creds = get_credentials()
    creds, project = google.auth.default()
    return build('people', 'v1', credentials=creds)

@mcp.tool()
def create_contact(name, email=None, phone=None):
    person = {'names': [{'displayName': name}]}
    if email:
        person['emailAddresses'] = [{'value': email}]
    if phone:
        person['phoneNumbers'] = [{'value': phone}]
    return service.people().createContact(body=person).execute()

@mcp.tool()
def read_contact(person_id):
    try:
        return service.people().get(resourceName=person_id, personFields='names,emailAddresses,phoneNumbers').execute()
    except Exception as e:
        return None

@mcp.tool()
def update_contact(person_id, new_name=None, new_email=None, new_phone=None):
    try:
        person = service.people().get(resourceName=person_id, personFields='names,emailAddresses,phoneNumbers').execute()
        if new_name:
            person['names'] = [{'displayName': new_name}]
        if new_email:
            person['emailAddresses'] = [{'value': new_email}]
        elif 'emailAddresses' not in person:
            person['emailAddresses'] = []
        if new_phone:
            person['phoneNumbers'] = [{'value': new_phone}]
        elif 'phoneNumbers' not in person:
            person['phoneNumbers'] = []
        return service.people().updateContact(resourceName=person_id, body=person).execute()
    except Exception as e:
        return None

@mcp.tool()
def delete_contact(person_id):
    try:
        service.people().deleteContact(resourceName=person_id).execute()
        return True
    except Exception as e:
        return False

@mcp.tool()
def list_contacts(page_size=10):
    results = service.people().connections().list(
        resourceName='people/me',
        personFields='names,emailAddresses,phoneNumbers',
        pageSize=page_size).execute()
    return results.get('connections', [])


if __name__ == "__main__":
    try:
      service = build("people", "v1", credentials=get_credentials())
    except Exception as e:
      print(e)
    mcp.run()