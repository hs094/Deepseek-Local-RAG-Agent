# Google Drive Picker Component for Streamlit

This is a custom Streamlit component that integrates the Google Drive Picker API, allowing users to select files from their Google Drive directly within a Streamlit application.

## Features

- Seamless integration with Google Drive
- File selection with visual feedback
- Support for multiple file selection
- Filtering by file type (PDF, documents, etc.)
- Responsive design

## Installation

1. Make sure you have Node.js and npm installed
2. Navigate to the frontend directory:
   ```bash
   cd google_drive_picker/frontend
   ```
3. Install dependencies:
   ```bash
   npm install
   ```
4. Build the component:
   ```bash
   npm run build
   ```

## Usage

```python
import streamlit as st
from google_drive_picker import google_drive_picker

# Initialize the component with OAuth token, API key, and App ID
selected_files = google_drive_picker(
    oauth_token="your_oauth_token",
    api_key="your_api_key",
    app_id="your_app_id",
    height=300,
    key="google_drive_picker"
)

# Process selected files
if selected_files:
    st.write(f"Selected {len(selected_files)} files")
    for file in selected_files:
        st.write(f"File: {file['name']}, Type: {file['mimeType']}")
```

## Requirements

- Google Cloud project with Drive API and Picker API enabled
- OAuth 2.0 credentials
- API key

## Development

To run the component in development mode:

1. Start the React development server:
   ```bash
   cd google_drive_picker/frontend
   npm start
   ```

2. In a separate terminal, run the Streamlit app:
   ```bash
   streamlit run google_drive_picker/__init__.py
   ```

## License

MIT
