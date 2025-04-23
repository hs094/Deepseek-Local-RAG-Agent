import React, { useEffect, useState } from "react"
import ReactDOM from "react-dom"
import { Streamlit, withStreamlitConnection } from "streamlit-component-lib"

/**
 * This is a React-based component template for a custom Streamlit component.
 * The `withStreamlitConnection` function wraps your component and manages
 * the communication between your component and the Streamlit app.
 */
const GoogleDrivePicker = ({ args, disabled }) => {
  const { oauth_token, api_key, app_id, height } = args
  const [pickerApiLoaded, setPickerApiLoaded] = useState(false)
  const [authStatus, setAuthStatus] = useState("Initializing...")
  const [selectedFiles, setSelectedFiles] = useState([])
  const [buttonDisabled, setButtonDisabled] = useState(true)
  const [statusColor, setStatusColor] = useState("#666")

  // Load the Google Picker API
  useEffect(() => {
    // Load the Google API client
    const script = document.createElement("script")
    script.src = "https://apis.google.com/js/api.js"
    script.async = true
    script.defer = true
    script.onload = () => {
      window.gapi.load("picker", () => {
        setPickerApiLoaded(true)
        console.log("Google Picker API loaded")
        setAuthStatus("Google Picker API loaded")
        checkButtonState()
      })
    }
    document.body.appendChild(script)

    // Cleanup
    return () => {
      document.body.removeChild(script)
    }
  }, [])

  // Check if we can enable the button
  useEffect(() => {
    checkButtonState()
  }, [pickerApiLoaded, oauth_token])

  const checkButtonState = () => {
    if (pickerApiLoaded && oauth_token) {
      setButtonDisabled(false)
      setAuthStatus("Ready to select files")
      setStatusColor("#4CAF50")
    } else if (!pickerApiLoaded) {
      setButtonDisabled(true)
      setAuthStatus("Loading Google Picker API...")
      setStatusColor("#FFA500")
    } else if (!oauth_token) {
      setButtonDisabled(true)
      setAuthStatus("Please authenticate with Google Drive")
      setStatusColor("#F44336")
    }
  }

  // Create and render the Google Picker
  const createPicker = () => {
    if (!pickerApiLoaded || !oauth_token) {
      setAuthStatus("Google Picker API not loaded or OAuth token not available")
      setStatusColor("#F44336")
      return
    }

    setAuthStatus("Opening Google Drive Picker...")
    setStatusColor("#FFA500")

    try {
      const picker = new window.google.picker.PickerBuilder()
        .addView(window.google.picker.ViewId.DOCS)
        .addView(window.google.picker.ViewId.PDFS)
        .enableFeature(window.google.picker.Feature.MULTISELECT_ENABLED)
        .setOAuthToken(oauth_token)
        .setDeveloperKey(api_key)
        .setAppId(app_id)
        .setCallback(pickerCallback)
        .build()

      picker.setVisible(true)
    } catch (error) {
      console.error("Error creating picker:", error)
      setAuthStatus(`Error: ${error.message}`)
      setStatusColor("#F44336")
    }
  }

  // Handle the picker callback
  const pickerCallback = (data) => {
    if (data[window.google.picker.Response.ACTION] === window.google.picker.Action.PICKED) {
      const docs = data[window.google.picker.Response.DOCUMENTS]
      const files = docs.map(doc => ({
        id: doc[window.google.picker.Document.ID],
        name: doc[window.google.picker.Document.NAME],
        url: doc[window.google.picker.Document.URL],
        mimeType: doc[window.google.picker.Document.MIME_TYPE],
        iconUrl: doc[window.google.picker.Document.ICON_URL]
      }))

      setSelectedFiles(files)
      setAuthStatus(`Selected ${files.length} file(s)`)
      setStatusColor("#4CAF50")

      // Send the selected files to Streamlit
      Streamlit.setComponentValue(JSON.stringify(files))
    } else if (data[window.google.picker.Response.ACTION] === window.google.picker.Action.CANCEL) {
      setAuthStatus("File selection canceled")
      setStatusColor("#FFA500")
    }
  }

  // Render the component
  return (
    <div style={{ fontFamily: "Arial, sans-serif", padding: "10px", height: `${height}px` }}>
      <button
        onClick={createPicker}
        disabled={buttonDisabled}
        style={{
          backgroundColor: buttonDisabled ? "#cccccc" : "#4285F4",
          color: "white",
          border: "none",
          borderRadius: "4px",
          padding: "10px 16px",
          fontSize: "14px",
          cursor: buttonDisabled ? "not-allowed" : "pointer",
          width: "100%",
          marginBottom: "10px"
        }}
      >
        Select Files from Google Drive
      </button>

      <div style={{ fontSize: "12px", color: statusColor, marginBottom: "10px" }}>
        {authStatus}
      </div>

      {selectedFiles.length > 0 && (
        <div>
          <div style={{ fontSize: "14px", marginBottom: "5px" }}>Selected files:</div>
          <div style={{ maxHeight: "150px", overflowY: "auto" }}>
            {selectedFiles.map((file, index) => (
              <div
                key={index}
                style={{
                  backgroundColor: "#f1f3f4",
                  borderRadius: "4px",
                  padding: "5px 10px",
                  margin: "5px 0",
                  display: "flex",
                  alignItems: "center",
                  fontSize: "12px"
                }}
              >
                <span style={{ marginRight: "8px" }}>📄</span>
                <span>{file.name}</span>
                <span style={{ 
                  color: file.mimeType === "application/pdf" ? "green" : "red", 
                  marginLeft: "5px" 
                }}>
                  {file.mimeType === "application/pdf" ? "✓ Will be processed" : "✗ Not a PDF"}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// "withStreamlitConnection" is a wrapper function. It bootstraps the
// connection between your component and the Streamlit app, and handles
// passing arguments from Python -> Component.
const GoogleDrivePickerWithConnection = withStreamlitConnection(GoogleDrivePicker)

// This is the entry point for the component. It renders the wrapped component
// and manages the communication with the Streamlit app.
ReactDOM.render(
  <GoogleDrivePickerWithConnection />,
  document.getElementById("root")
)
