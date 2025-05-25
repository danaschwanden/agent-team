import requests
from requests.auth import HTTPBasicAuth
from urllib.parse import urljoin
import xml.etree.ElementTree as ET
import uuid

class SabreBaikalCardDAVClient:
    """
    A CardDAV client for interacting with a SabreDAV/Baikal server.
    Implements basic CRUD operations for address book objects (vCards).
    """

    def __init__(self, base_url, base_path, username, password, addressbook_path='addressbooks/USERNAME/default/'):
        """
        Initializes the CardDAV client.

        Args:
            base_url (str): The base URL of the SabreDAV/Baikal server (e.g., 'https://your.baikal.server').
            base_path (str): The base PATH of the SabreDAV/Baikal server (e.g., '/dav.php').
            username (str): The username for authentication.
            password (str): The password for authentication.
            addressbook_path (str, optional): The path to the user's default address book.
                                               Replace 'USERNAME' with the actual username.
                                               Defaults to 'addressbooks/users/USERNAME/default/'.
        """
        self.base_url = base_url.rstrip('/')
        self.base_path = base_path.rstrip('/')
        self.username = username
        self.password = password
        self.auth = HTTPBasicAuth(self.username, self.password)
        self.addressbook_path = addressbook_path.replace('USERNAME', self.username).strip('/')
        self.addressbook_url = self.base_url + '/' + self.base_path + '/' + self.addressbook_path + '/'
        self.headers = {'Content-Type': 'application/xml; charset=utf-8'}

    def _dav_request(self, method, url, data=None, headers=None):
        """
        Makes a generic DAV request with authentication and error handling.
        """
        all_headers = self.headers.copy()
        if headers:
            all_headers.update(headers)

        try:
            response = requests.request(method, url, auth=self.auth, data=data, headers=all_headers)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            return response
        except requests.exceptions.RequestException as e:
            print(f"Error during {method} request to {url}: {e}")
            if response is not None:
                print(f"Response status code: {response.status_code}")
                print(f"Response content: {response.content.decode('utf-8', 'ignore')}")
            return None

    def list_contacts(self):
        """
        Lists all contact objects (vCards) in the address book.

        Returns:
            list: A list of dictionaries, where each dictionary contains the 'href'
                  and 'etag' of a contact. Returns None on error.
        """
        url = self.addressbook_url
        print(f" list contacts for addressbook_url: {self.addressbook_url}")
        props = [
            ('DAV:', 'getetag'),
        ]
        propfind_body = self._build_propfind_request(props)
        headers = {'Depth': '1'}  # Request properties for the address book and its contents

        response = self._dav_request('PROPFIND', url, data=propfind_body, headers=headers)
        if response and response.status_code == 207:  # Multi-Status
            tree = ET.fromstring(response.content)
            contacts = []
            for response_element in tree.findall('.//{DAV:}response'):
                href_element = response_element.find('{DAV:}href')
                propstat_element = response_element.find('.//{DAV:}propstat')
                if href_element is not None and propstat_element is not None and propstat_element.find('{DAV:}status').text.startswith('HTTP/1.1 200'):
                    etag_element = propstat_element.find('.//{DAV:}getetag')
                    # Exclude the addressbook itself from the list of contacts
                    if etag_element is not None and href_element.text.strip('/') != self.addressbook_path:
                        contacts.append({'href': href_element.text, 'etag': etag_element.text})
            return contacts
        return None

    def create_contact(self, vcard_data):
        """
        Creates a new contact object (vCard) in the address book.

        Args:
            vcard_data (str): The vCard data as a string.

        Returns:
            str: The 'href' of the newly created contact object on success, None on error.
        """
        uid = uuid.uuid4()
        filename = f"{uid}.vcf"
        url = urljoin(self.addressbook_url, filename)
        headers = {'Content-Type': 'text/vcard; charset=utf-8'}
        response = self._dav_request('PUT', url, data=vcard_data.encode('utf-8'), headers=headers)
        if response and response.status_code == 201:  # Created
            return url
        return None

    def read_contact(self, contact_href):
        """
        Reads the vCard data of a specific contact object.

        Args:
            contact_href (str): The full 'href' of the contact object.

        Returns:
            str: The vCard data as a string on success, None on error.
        """
        response = self._dav_request('GET', contact_href)
        if response and response.status_code == 200:
            return response.content.decode('utf-8')
        return None

    def update_contact(self, contact_href, vcard_data, etag=None):
        """
        Updates the vCard data of an existing contact object.

        Args:
            contact_href (str): The full 'href' of the contact object.
            vcard_data (str): The new vCard data as a string.
            etag (str, optional): The current entity tag (etag) of the contact.
                                 If provided, used for optimistic locking. Defaults to None.

        Returns:
            bool: True on successful update, False on error.
        """
        headers = {'Content-Type': 'text/vcard; charset=utf-8'}
        if etag:
            headers['If-Match'] = etag
        response = self._dav_request('PUT', contact_href, data=vcard_data.encode('utf-8'), headers=headers)
        if response and response.status_code == 204:  # No Content (successful update)
            return True
        elif response and response.status_code == 412:  # Precondition Failed (etag mismatch)
            print("Error: ETag mismatch. Contact has been updated by someone else.")
        return False

    def delete_contact(self, contact_href, etag=None):
        """
        Deletes a specific contact object.

        Args:
            contact_href (str): The full 'href' of the contact object.
            etag (str, optional): The current entity tag (etag) of the contact.
                                 If provided, used for optimistic locking. Defaults to None.

        Returns:
            bool: True on successful deletion, False on error.
        """
        headers = {}
        if etag:
            headers['If-Match'] = etag
        response = self._dav_request('DELETE', contact_href, headers=headers)
        if response and response.status_code == 204:  # No Content (successful deletion)
            return True
        elif response and response.status_code == 412:  # Precondition Failed (etag mismatch)
            print("Error: ETag mismatch. Contact has been updated by someone else.")
        return False

    def _build_propfind_request(self, properties):
        """
        Builds the XML body for a PROPFIND request.

        Args:
            properties (list): A list of tuples, where each tuple contains the
                               (namespace, property_name).

        Returns:
            bytes: The XML body as bytes.
        """
        # Define DAV namespace for XML
        DAV_NS = "DAV:"
        root = ET.Element(f'{{{DAV_NS}}}propfind')
        prop = ET.SubElement(root, f'{{{DAV_NS}}}prop')
        for namespace, prop_name in properties:
            ET.SubElement(prop, f'{{{namespace}}}{prop_name}')
        return ET.tostring(root, encoding='utf-8')

if __name__ == '__main__':
    # --- Configuration ---
    # IMPORTANT: Replace these with your actual Sabre Baikal server details
    SERVER_URL = 'http://localhost:8040/'
    BASE_PATH = 'dav.php'
    USERNAME = 'dan'
    PASSWORD = ''

    client = SabreBaikalCardDAVClient(SERVER_URL, BASE_PATH, USERNAME, PASSWORD, 'addressbooks/USERNAME/agents/')

    # --- Example Usage ---

    # 1. List Contacts
    print("--- Listing Contacts ---")
    contacts = client.list_contacts()
    if contacts:
        for contact in contacts:
            print(f"  - Href: {contact['href']}, ETag: {contact['etag']}")
    else:
        print("  Could not list contacts or no contacts found.")

    # 2. Create Contact
    print("\n--- Creating Contact ---")
    new_vcard = """BEGIN:VCARD
VERSION:3.0
FN:Alice Wonderland
N:Wonderland;Alice;;;
TEL;TYPE=HOME:+48-111-222-333
EMAIL;TYPE=INTERNET:alice.w@example.com
END:VCARD
"""
    new_contact_href = client.create_contact(new_vcard)
    if new_contact_href:
        print(f"  Contact created successfully at: {new_contact_href}")

        # 3. Read Contact
        print("\n--- Reading Contact ---")
        read_vcard = client.read_contact(new_contact_href)
        if read_vcard:
            print("  --- vCard Data ---")
            print(read_vcard)

            # To perform an update or delete with optimistic locking,
            # you need the current ETag. Let's list contacts again to get it.
            print("\n--- Re-listing contacts to get current ETag ---")
            current_contacts = client.list_contacts()
            current_etag = None
            if current_contacts:
                for c in current_contacts:
                    href = client.base_url+c['href']
                    print(f"  -- Href: {new_contact_href}")
                    print(f"  -- Href: {href}, ETag: {c['etag']}")
                    if href == new_contact_href:
                        current_etag = c['etag']
                        print(f"  Found current ETag for {new_contact_href}: {current_etag}")
                        break
            
            if current_etag:
                # 4. Update Contact
                print("\n--- Updating Contact ---")
                updated_vcard = """BEGIN:VCARD
VERSION:3.0
FN:Alice L. Wonderland
N:Wonderland;Alice;L.;;
TEL;TYPE=WORK:+48-999-888-777
EMAIL;TYPE=INTERNET:alice.l.w@example.com
END:VCARD
"""
                updated = client.update_contact(new_contact_href, updated_vcard, etag=current_etag)
                if updated:
                    print("  Contact updated successfully.")

                    # Verify update by reading again
                    print("\n--- Reading Updated Contact ---")
                    read_updated_vcard = client.read_contact(new_contact_href)
                    if read_updated_vcard:
                        print("  --- Updated vCard Data ---")
                        print(read_updated_vcard)

                    # Get the new ETag after update for deletion
                    print("\n--- Re-listing contacts to get new ETag for deletion ---")
                    final_contacts = client.list_contacts()
                    final_etag = None
                    if final_contacts:
                        for c in final_contacts:
                            href = client.base_url+c['href']
                            print(f"  ----- Href: {href}, ETag: {c['etag']}")
                            if href == new_contact_href:
                                final_etag = c['etag']
                                print(f"  Found new ETag for {new_contact_href}: {final_etag}")
                                break

                    if final_etag:
                        # 5. Delete Contact
                        print("\n--- Deleting Contact ---")
                        deleted = client.delete_contact(new_contact_href, etag=final_etag)
                        if deleted:
                            print(f"  Contact at {new_contact_href} deleted successfully.")
                        else:
                            print(f"  Could not delete contact at {new_contact_href}.")
                    else:
                        print("  Could not retrieve new ETag for deletion. Skipping delete.")

                else:
                    print("  Could not update contact.")
            else:
                print("  Could not retrieve ETag for update. Skipping update and delete.")
        else:
            print(f"  Could not read contact at: {new_contact_href}")

    else:
        print("  Could not create contact.")

    print("\n--- Final List Contacts ---")
    contacts_after_ops = client.list_contacts()
    if contacts_after_ops:
        for contact in contacts_after_ops:
            print(f"  - Href: {contact['href']}, ETag: {contact['etag']}")
    else:
        print("  No contacts remaining or could not list contacts.")