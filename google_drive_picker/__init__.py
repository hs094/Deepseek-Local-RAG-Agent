import os
import streamlit.components.v1 as components
import json

# Create a _RELEASE constant. We'll set this to False while we're developing
# the component, and True when we're ready to package and distribute it.
_RELEASE = False

# Declare a Streamlit component. `declare_component` returns a function
# that is used to create instances of the component. We're naming this
# function "_component_func", with an underscore prefix, because we don't want
# to expose it directly to users. Instead, we will create a custom wrapper
# function, below, that will serve as our component's public API.

# It's important to note that this call to `declare_component` is,
# effectively, the *definition* of our component, with its mixins, JavaScript
# code, and styling. The component will not render if this function is not called.

if not _RELEASE:
    # During development, we can use the hot-reloading version
    _component_func = components.declare_component(
        "google_drive_picker",
        url="http://localhost:3001",
    )
else:
    # When we're distributing a production version of the component, we'll
    # replace the `url` param with `path`
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    build_dir = os.path.join(parent_dir, "frontend/build")
    _component_func = components.declare_component("google_drive_picker", path=build_dir)


# Create a wrapper function for the component. This is an optional
# best practice - we could simply expose the component function returned by
# `declare_component` and call it done. The wrapper allows us to customize
# our component's API: we can pre-process its input args, post-process its
# output value, and add a docstring for users.
def google_drive_picker(
    oauth_token,
    api_key,
    app_id,
    key=None,
    height=300,
):
    """Create a new instance of "google_drive_picker".

    Parameters
    ----------
    oauth_token: str
        The OAuth token for Google Drive API
    api_key: str
        The Google API key
    app_id: str
        The Google App ID
    key: str or None
        An optional key that uniquely identifies this component. If this is
        None, and the component's arguments are changed, the component will
        be re-mounted in the Streamlit frontend and lose its current state.
    height: int
        Height of the component in pixels

    Returns
    -------
    list
        List of selected files from Google Drive
    """
    # Call through to our private component function. Arguments we pass here
    # will be sent to the frontend, where they'll be available in an "args"
    # dictionary.
    #
    # "default" is a special argument that specifies the initial return
    # value of the component before the user has interacted with it.
    component_value = _component_func(
        oauth_token=oauth_token,
        api_key=api_key,
        app_id=app_id,
        height=height,
        key=key,
        default=None,
    )

    # Parse the JSON string returned from the component
    if component_value is not None:
        try:
            return json.loads(component_value)
        except json.JSONDecodeError:
            return None
    
    return None


# Add some test code to play with the component while it's in development.
# During development, we can run this just as we would any other Streamlit
# app: `$ streamlit run google_drive_picker/__init__.py`
if not _RELEASE:
    import streamlit as st

    st.subheader("Component with constant args")

    # Create an instance of our component with a constant `name` arg, and
    # print its output value.
    oauth_token = st.text_input("OAuth Token")
    api_key = st.text_input("API Key")
    app_id = st.text_input("App ID")
    
    if oauth_token and api_key and app_id:
        selected_files = google_drive_picker(
            oauth_token=oauth_token,
            api_key=api_key,
            app_id=app_id,
        )
        
        if selected_files:
            st.write("Selected files:", selected_files)
