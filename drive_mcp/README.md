# Google Drive MCP (Model Context Protocol)

This module provides a clean interface for Google Drive authentication and file operations. It handles authentication, token caching, and file search operations.

## Features

- Google Drive authentication with OAuth2
- Local caching of authentication tokens
- File search functionality
- File content retrieval
- Utility functions for formatting file information

## Usage

### Basic Usage

```python
from mcp.gdrive import GoogleDriveClient

# Create a client
client = GoogleDriveClient()

# Authenticate
if client.authenticate():
    # Search for files
    files = client.search_files("document")
    
    # Process results
    for file in files:
        print(f"Found file: {file['name']}")
```

### Saving Credentials

```python
# Check if credentials exist
if not client.credentials_exist():
    # Save credentials from uploaded content
    with open('path/to/credentials.json', 'rb') as f:
        client.save_credentials_file(f.read())
```

### Getting File Content

```python
# Get file content
file_id = "your_file_id"
content = client.get_file_content(file_id)

# Process the content
# For example, if it's a text file:
text = content.read().decode('utf-8')
print(text)
```

## Integration with Streamlit

See `app_mcp.py` for an example of how to integrate this module with a Streamlit application.

## Example Server

The `example/main.py` file demonstrates how to create a simple server that provides Google Drive functionality using this MCP module.

## API Reference

### `GoogleDriveClient`

The main class for interacting with Google Drive.

#### Methods

- `__init__(credentials_file, token_pickle_file, scopes)`: Initialize the client
- `credentials_exist()`: Check if credentials file exists
- `save_credentials_file(content)`: Save credentials from content
- `authenticate()`: Authenticate with Google Drive
- `search_files(query, folder_id, page_size, order_by)`: Search for files
- `get_file_content(file_id)`: Get file content

### Utility Functions

- `format_file_size(size)`: Format file size to human-readable format
- `format_date(date_string)`: Format date string to readable format
- `get_file_icon(mime_type)`: Get appropriate icon for file type
