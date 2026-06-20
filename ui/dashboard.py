import streamlit as st
import requests
import json
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="P2P Network Dashboard", layout="wide")
st.title("🌐 P2P Document Synchronization Dashboard")
st_autorefresh(interval=1000)
# 1. Read the auto-discovery registry
try:
    with open("network_registry.json", "r") as f:
        registry = json.load(f)
        nodes = registry.get("nodes", [])
except FileNotFoundError:
    st.error("Could not find network_registry.json. Please run spawn_network.py first!")
    st.stop()

# 2. Sidebar Controls (The Remote Control)
st.sidebar.header("📝 Edit Document")
selected_node_id = st.sidebar.selectbox("Select Node to Edit", [n["id"] for n in nodes])
new_content = st.sidebar.text_input("New Document Content")

if st.sidebar.button("Submit Edit"):
    # Find the correct API port for the node we selected
    target_port = next(n["api_port"] for n in nodes if n["id"] == selected_node_id)
    try:
        url = f"http://127.0.0.1:{target_port}/edit"
        payload = {"document": {"content": new_content}}
        
        # Fire the POST request!
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            st.sidebar.success(f"Successfully sent edit to {selected_node_id}!")
        else:
            st.sidebar.error(f"Error: {response.text}")
    except requests.exceptions.RequestException as e:
        st.sidebar.error(f"Failed to connect to {selected_node_id}: {e}")

# Manual polling button
st.button("🔄 Refresh Network State")
st.markdown("---")

# 3. Display Node Cards
st.subheader("🖥️ Live Node States")

# 1. FETCH FIRST (Super fast, invisible to the user)
fetched_states = []
for node in nodes:
    try:
        url = f"http://127.0.0.1:{node['api_port']}/state"
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            raw_json = response.json()
            fetched_states.append({"status": "online", "data": raw_json.get("document", {})})
        else:
            fetched_states.append({"status": "api_error", "code": response.status_code})
    except requests.exceptions.RequestException:
        fetched_states.append({"status": "offline"})

# 2. DRAW SECOND (Draws all 3 instantly at the exact same time)
cols = st.columns(len(nodes))

for i, node in enumerate(nodes):
    state_info = fetched_states[i]
    with cols[i]:
        st.markdown(f"### {node['id']}")
        st.caption(f"API: {node['api_port']} | P2P: {node['p2p_port']}")
        
        if state_info["status"] == "online":
            st.success("🟢 Online")
            doc = state_info["data"]
            
            # Render the CRDT State instantly!
            st.metric("Document Version", doc.get("version", 0))
            
            st.markdown("**Document Content:**")
            st.info(doc.get("content", "") if doc.get("content") else "(Empty)")
            
            st.caption(f"Last modified by Peer ID: \n`{doc.get('last_mod_by', 'N/A')}`")
            
        elif state_info["status"] == "api_error":
            st.warning(f"🟡 API Error: {state_info['code']}")
        else:
            st.error("🔴 Node Offline")
 