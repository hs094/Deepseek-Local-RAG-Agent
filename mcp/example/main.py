"""
Example MCP Server Implementation

This example demonstrates how to use the Google Drive MCP module
to create a simple server that provides Google Drive functionality.
"""

import os
import sys
import json
from typing import Dict, Any, List

# Add the parent directory to the path so we can import the MCP module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gdrive import GoogleDriveClient, format_file_size, format_date, get_file_icon

class MCPServer:
    """
    A simple MCP server implementation that provides Google Drive functionality.
    """
    
    def __init__(self):
        """Initialize the MCP server with a Google Drive client."""
        self.gdrive_client = GoogleDriveClient()
        self.authenticated = False
    
    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle an MCP request.
        
        Args:
            request: A dictionary containing the request parameters
            
        Returns:
            A dictionary containing the response
        """
        action = request.get('action')
        
        if action == 'check_credentials':
            return self._handle_check_credentials()
        elif action == 'save_credentials':
            return self._handle_save_credentials(request.get('credentials_content'))
        elif action == 'authenticate':
            return self._handle_authenticate()
        elif action == 'search_files':
            return self._handle_search_files(
                request.get('query', ''),
                request.get('folder_id')
            )
        else:
            return {
                'status': 'error',
                'message': f'Unknown action: {action}'
            }
    
    def _handle_check_credentials(self) -> Dict[str, Any]:
        """Check if credentials file exists."""
        exists = self.gdrive_client.credentials_exist()
        return {
            'status': 'success',
            'credentials_exist': exists
        }
    
    def _handle_save_credentials(self, credentials_content: str) -> Dict[str, Any]:
        """Save credentials from content."""
        if not credentials_content:
            return {
                'status': 'error',
                'message': 'No credentials content provided'
            }
        
        try:
            # Convert from base64 or other format if needed
            content_bytes = credentials_content.encode('utf-8')
            self.gdrive_client.save_credentials_file(content_bytes)
            return {
                'status': 'success',
                'message': 'Credentials saved successfully'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to save credentials: {str(e)}'
            }
    
    def _handle_authenticate(self) -> Dict[str, Any]:
        """Authenticate with Google Drive."""
        try:
            success = self.gdrive_client.authenticate()
            self.authenticated = success
            
            if success:
                return {
                    'status': 'success',
                    'authenticated': True,
                    'message': 'Authentication successful'
                }
            else:
                return {
                    'status': 'error',
                    'authenticated': False,
                    'message': 'Authentication failed. Please check your credentials.'
                }
        except Exception as e:
            return {
                'status': 'error',
                'authenticated': False,
                'message': f'Authentication error: {str(e)}'
            }
    
    def _handle_search_files(self, query: str, folder_id: str = None) -> Dict[str, Any]:
        """Search for files in Google Drive."""
        if not self.authenticated:
            auth_result = self._handle_authenticate()
            if auth_result.get('status') != 'success':
                return auth_result
        
        try:
            files = self.gdrive_client.search_files(query, folder_id)
            
            # Process files to add formatted information
            processed_files = []
            for file in files:
                processed_file = {
                    'id': file.get('id'),
                    'name': file.get('name'),
                    'mimeType': file.get('mimeType'),
                    'webViewLink': file.get('webViewLink'),
                    'iconLink': file.get('iconLink'),
                    'size': file.get('size'),
                    'formatted_size': format_file_size(file.get('size')),
                    'modifiedTime': file.get('modifiedTime'),
                    'formatted_date': format_date(file.get('modifiedTime')),
                    'icon': get_file_icon(file.get('mimeType', '')),
                    'is_folder': 'folder' in file.get('mimeType', ''),
                    'parents': file.get('parents', [])
                }
                processed_files.append(processed_file)
            
            # Sort: folders first, then by name
            folders = [f for f in processed_files if f['is_folder']]
            regular_files = [f for f in processed_files if not f['is_folder']]
            
            return {
                'status': 'success',
                'query': query,
                'folder_id': folder_id,
                'total_files': len(processed_files),
                'folders': folders,
                'files': regular_files
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Search error: {str(e)}'
            }


def example_usage():
    """Example of how to use the MCP server."""
    server = MCPServer()
    
    # Check if credentials exist
    response = server.handle_request({'action': 'check_credentials'})
    print("Credentials check:", json.dumps(response, indent=2))
    
    # If credentials don't exist, you would typically save them here
    # response = server.handle_request({
    #     'action': 'save_credentials',
    #     'credentials_content': '...'  # Content of credentials.json
    # })
    
    # Authenticate
    response = server.handle_request({'action': 'authenticate'})
    print("Authentication:", json.dumps(response, indent=2))
    
    if response.get('status') == 'success' and response.get('authenticated'):
        # Search for files
        response = server.handle_request({
            'action': 'search_files',
            'query': 'document'
        })
        print("Search results:", json.dumps(response, indent=2))


if __name__ == "__main__":
    example_usage()
