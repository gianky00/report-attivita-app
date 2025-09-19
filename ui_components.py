import streamlit as st
import streamlit.components.v1 as components

def render_status_indicator():
    """
    Renders a component that displays the browser's online/offline status
    and returns the status string ('online' or 'offline') to the Python backend.
    """
    # The key is important to keep the component instance stable across reruns
    component_key = "online_status_component"

    html_code = f"""
    <div id="status-indicator-container" style="position: fixed; top: 10px; right: 10px; z-index: 1000; background-color: white; padding: 5px 10px; border-radius: 8px; border: 1px solid #dcdcdc; font-family: sans-serif; font-size: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);">
        <div id="status-indicator"></div>
    </div>
    <script>
        const statusIndicator = document.getElementById('status-indicator');
        const component_key = '{component_key}';

        function updateOnlineStatus() {{
            const isOnline = navigator.onLine;
            let statusValue;
            if (isOnline) {{
                statusIndicator.innerHTML = '<span>🟢 Connesso</span>';
                statusValue = 'online';
            }} else {{
                statusIndicator.innerHTML = '<span>🔴 Offline</span>';
                statusValue = 'offline';
            }}
            // Send the status back to Streamlit
            window.parent.postMessage({{
                isStreamlitMessage: true,
                type: 'streamlit:setComponentValue',
                key: component_key,
                value: statusValue
            }}, '*');
        }}

        // Add event listeners to update status on change
        window.addEventListener('online', updateOnlineStatus);
        window.addEventListener('offline', updateOnlineStatus);

        // Set initial status when the script loads
        // Use a small timeout to ensure the component is ready to receive the value
        setTimeout(updateOnlineStatus, 100);
    </script>
    """

    # The component's return value is the status string sent from JavaScript
    online_status = components.html(html_code, height=0, width=0, key=component_key)

    # Default to 'online' on the very first render before the JS has run
    return online_status or 'online'
