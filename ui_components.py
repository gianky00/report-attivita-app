import streamlit as st
import streamlit.components.v1 as components

def render_status_indicator():
    """
    Renders a component that displays the browser's online/offline status
    and returns the status string ('online' or 'offline') to the Python backend.
    """
    html_code = f"""
    <div id="status-indicator-container" style="position: fixed; top: 10px; right: 10px; z-index: 1000; background-color: white; padding: 5px 10px; border-radius: 8px; border: 1px solid #dcdcdc; font-family: sans-serif; font-size: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);">
        <div id="status-indicator"></div>
    </div>
    <script>
        const statusIndicator = document.getElementById('status-indicator');

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
            // Send the status back to Streamlit.
            // For st.components.v1.html, we don't need a key. Streamlit knows
            // which component sent the message.
            window.parent.postMessage({{
                isStreamlitMessage: true,
                type: 'streamlit:setComponentValue',
                value: statusValue
            }}, '*');
        }}

        window.addEventListener('online', updateOnlineStatus);
        window.addEventListener('offline', updateOnlineStatus);

        setTimeout(updateOnlineStatus, 100);
    </script>
    """

    # The 'key' argument is not supported by st.components.v1.html
    online_status = components.html(html_code, height=0, width=0)

    return online_status or 'online'
