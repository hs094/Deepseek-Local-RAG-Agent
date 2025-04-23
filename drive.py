"""
Google Drive File Browser using MCP

A Streamlit web application that allows you to browse and search your Google Drive files
with read-only access, using the Model Context Protocol (MCP) for Google Drive integration.
"""

import streamlit as st
import os
import sys
import json
from typing import Dict, Any, List, Optional

# Add the MCP module to the path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mcp'))

# Import the MCP module
from mcp.gdrive import GoogleDriveClient, format_file_size, format_date, get_file_icon

# Initialize the Google Drive client
@st.cache_resource
def get_gdrive_client():
    """Get or create a Google Drive client."""
    return GoogleDriveClient()

def main():
    st.title("Google Drive File Browser (MCP)")

    # Get the Google Drive client
    gdrive_client = get_gdrive_client()

    # Initialize session state variables
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'current_folder' not in st.session_state:
        st.session_state.current_folder = None
    if 'folder_stack' not in st.session_state:
        st.session_state.folder_stack = []
    if 'folder_names' not in st.session_state:
        st.session_state.folder_names = []

    # Sidebar for credentials upload, login, and search
    with st.sidebar:
        st.header("Google Drive Access")

        # Allow user to upload credentials.json if it doesn't exist
        if not gdrive_client.credentials_exist():
            st.info("Please upload your Google API credentials file (credentials.json)")
            uploaded_file = st.file_uploader("Upload credentials.json", type="json")

            if uploaded_file is not None:
                # Save the uploaded file
                gdrive_client.save_credentials_file(uploaded_file.getbuffer())
                st.success("Credentials file uploaded successfully!")

        # Login button in sidebar
        if gdrive_client.credentials_exist() and not st.session_state.authenticated:
            st.subheader("Authentication")
            st.write("Click the button below to authenticate with Google Drive.")

            if st.button("Login to Google Drive", use_container_width=True):
                with st.spinner("Authenticating..."):
                    authenticated = gdrive_client.authenticate()
                    if authenticated:
                        st.session_state.authenticated = True
                        st.rerun()
                    else:
                        st.error("Authentication failed. Please check your credentials.")

        # Search functionality in sidebar
        if st.session_state.authenticated:
            st.subheader("Search Files")
            search_query = st.text_input("🔍 Search for files", "")
            search_button = st.button("Search", use_container_width=True)

            # Navigation controls in sidebar
            if st.session_state.folder_stack:
                st.button("⬅️ Back", key="sidebar_back", on_click=lambda: (
                    setattr(st.session_state, 'current_folder', st.session_state.folder_stack.pop()),
                    st.session_state.folder_names.pop(),
                    setattr(st.session_state, 'current_folder', None) if not st.session_state.folder_stack else None,
                    st.rerun()
                ))

            st.button("🏠 Home", key="sidebar_home", on_click=lambda: (
                setattr(st.session_state, 'current_folder', None),
                setattr(st.session_state, 'folder_stack', []),
                setattr(st.session_state, 'folder_names', []),
                st.rerun()
            ))

            # Show current location
            if st.session_state.folder_names:
                st.caption(f"Current folder: {st.session_state.folder_names[-1]}")
            else:
                st.caption("Location: Root")

            # Display search results in sidebar if available
            if 'search_query' in locals() and search_query and search_button:
                with st.spinner("Searching..."):
                    files = gdrive_client.search_files(search_query, st.session_state.current_folder)

                    if not files:
                        st.info("No files found.")
                    else:
                        st.success(f"Found {len(files)} results")

                        # Create an expander for folders
                        folders = [f for f in files if f['mimeType'] == 'application/vnd.google-apps.folder']
                        if folders:
                            with st.expander(f"Folders ({len(folders)})", expanded=True):
                                for folder in folders:
                                    col1, col2, col3 = st.columns([3, 1, 1])
                                    with col1:
                                        if st.button(f"📁 {folder['name'][:20]}{'...' if len(folder['name']) > 20 else ''}",
                                                   key=f"sidebar_folder_{folder['id']}"):
                                            if st.session_state.current_folder:
                                                st.session_state.folder_stack.append(st.session_state.current_folder)
                                            else:
                                                st.session_state.folder_stack.append(None)
                                            st.session_state.current_folder = folder['id']
                                            st.session_state.folder_names.append(folder['name'])
                                            st.rerun()
                                    with col2:
                                        st.caption(format_date(folder.get('modifiedTime', '')))
                                    with col3:
                                        st.markdown(f"[↗]({folder['webViewLink']})")

                        # Create an expander for files
                        regular_files = [f for f in files if f['mimeType'] != 'application/vnd.google-apps.folder']
                        if regular_files:
                            with st.expander(f"Files ({len(regular_files)})", expanded=True):
                                for file in regular_files:
                                    col1, col2, col3 = st.columns([3, 1, 1])
                                    with col1:
                                        icon = get_file_icon(file['mimeType'])
                                        st.write(f"{icon} {file['name'][:20]}{'...' if len(file['name']) > 20 else ''}")
                                    with col2:
                                        st.caption(f"{format_file_size(file.get('size'))}")
                                    with col3:
                                        st.markdown(f"[↗]({file['webViewLink']})")

    # Main content area
    if not gdrive_client.credentials_exist():
        st.warning("Please upload your credentials.json file in the sidebar to continue.")
        st.info("You can create credentials.json from the Google Cloud Console:")
        st.markdown("""
        1. Go to [Google Cloud Console](https://console.cloud.google.com/)
        2. Create a new project
        3. Enable the Google Drive API
        4. Create OAuth 2.0 credentials (Desktop application)
        5. Download the credentials as JSON
        """)
        return

    # Main content area instructions when not authenticated
    if not st.session_state.authenticated:
        st.header("Connect to Google Drive")
        st.write("Please authenticate with Google Drive using the login button in the sidebar.")
        st.info("Once authenticated, you'll be able to search for and access your Google Drive files.")
    else:
        # User is authenticated, show file browser

        # Main area header with breadcrumb navigation
        st.header("Google Drive Files")
        breadcrumb = "📂 Home"
        for folder_name in st.session_state.folder_names:
            breadcrumb += f" > {folder_name}"
        st.write(breadcrumb)

        # Main area instructions
        if 'search_query' in locals() and search_query and search_button:
            # Show a message about where to find results
            st.info("Search results are displayed in the sidebar. Click on folders to navigate or use the links to open files in Google Drive.")

            # Show a placeholder for the selected file details (could be expanded in the future)
            st.subheader("File Details")
            st.write("Select a file from the sidebar to view its details here.")

        elif 'search_query' in locals() and not search_query and search_button:
            st.warning("Please enter a search term to find files.")
        elif st.session_state.authenticated:
            st.info("Enter a search term in the sidebar and click 'Search' to find files in your Google Drive.")
if __name__ == "__main__":
    main()
