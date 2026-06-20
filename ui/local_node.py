import streamlit as st
import requests
import json
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="P2P Document Editor", layout="wide", initial_sidebar_state="collapsed")

# ── Custom CSS: Google Docs-inspired document editor ──
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

/* Reset Streamlit defaults */
.stApp {
    font-family: 'Inter', sans-serif;
}
header[data-testid="stHeader"] { background: transparent; }
.block-container {
    max-width: 900px;
    padding-top: 1rem;
    padding-bottom: 2rem;
}

/* ── Top toolbar bar ── */
.toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--secondary-background-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 8px 20px;
    margin-bottom: 12px;
}
.toolbar .left { display: flex; align-items: center; gap: 12px; }
.toolbar .doc-icon { font-size: 28px; }
.toolbar .room-name {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-color);
}
.toolbar .node-badge {
    background: rgba(26, 115, 232, 0.2);
    color: #4da8da;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
}
.toolbar .right {
    display: flex;
    align-items: center;
    gap: 16px;
    font-size: 12px;
}
.toolbar .version-pill {
    background: var(--secondary-background-color);
    padding: 3px 10px;
    border-radius: 12px;
    font-weight: 500;
}

/* ── Streamlit widget overrides for Document Page ── */
/* Make the text area look like a physical document page */
div[data-testid="stTextArea"] > div:first-child {
    background: var(--secondary-background-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 20px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.1);
}

.stTextArea textarea {
    font-family: 'Inter', sans-serif !important;
    font-size: 16px !important;
    line-height: 1.75 !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    resize: none !important;
    min-height: 50vh !important;
    background: transparent !important;
}
.stTextArea textarea:focus {
    border: none !important;
    box-shadow: none !important;
}
div[data-testid="stTextArea"] label { display: none; }

/* ── Footer metadata ── */
.doc-footer {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    margin-top: 16px;
    border-top: 1px solid var(--border-color);
    font-size: 11px;
    opacity: 0.7;
}

/* Hide Streamlit branding */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
</style>
""",
    unsafe_allow_html=True,
)

st_autorefresh(interval=1000, key="network_poll")

# ── 1. Read the auto-discovery registry ──
try:
    with open("network_registry.json", "r") as f:
        registry = json.load(f)
        nodes = registry.get("nodes", [])
except FileNotFoundError:
    st.error("Could not find network_registry.json. Please run spawn_network.py first!")
    st.stop()


import time

# ── 2. Node Assignment via URL query params & Leases ──
@st.cache_resource
def get_node_leases():
    return {} # { node_id: last_seen_timestamp }


leases = get_node_leases()
current_time = time.time()
params = st.query_params

# Clean up expired leases (older than 3 seconds)
for nid in list(leases.keys()):
    if current_time - leases[nid] > 3:
        del leases[nid]

# Check if this tab already has a node assigned via URL
assigned_node = None
if "node" in params:
    requested_id = params["node"]
    match = [n for n in nodes if n["id"] == requested_id]
    if match:
        assigned_node = match[0]

# If no valid assignment, grab the first free node
if not assigned_node:
    free_nodes = [n for n in nodes if n["id"] not in leases]
    if not free_nodes:
        st.error(
            "All local nodes are currently in use! Close another tab to free up a node."
        )
        st.stop()
    assigned_node = free_nodes[0]
    st.query_params["node"] = assigned_node["id"]

# Renew the lease for our assigned node
leases[assigned_node["id"]] = current_time

target_port = assigned_node["api_port"]
node_id = assigned_node["id"]

# ── 3. Sidebar: Room Switching ──
with st.sidebar:
    st.markdown(f"### 🖥️ {node_id}")
    st.caption(f"API Port: {target_port}")
    st.markdown("---")
    st.markdown("#### 🚪 Switch Room")
    new_room = st.text_input("Room Name", value="default-topic", label_visibility="collapsed")
    if st.button("Join Room", use_container_width=True):
        try:
            requests.post(
                f"http://127.0.0.1:{target_port}/topic", json={"topic": new_room}
            )
            st.success(f"Joined **{new_room}**")
        except Exception as e:
            st.error(f"Failed: {e}")

# ── 4. Fetch Node State ──
try:
    response = requests.get(f"http://127.0.0.1:{target_port}/state", timeout=2)
    if response.status_code != 200:
        st.warning("API returned an error.")
        st.stop()
    raw_json = response.json()
    doc = raw_json.get("document", {})
    current_topic = raw_json.get("current_topic", "unknown")
    version = doc.get("version", 0)
    content = doc.get("content", "")
    last_mod = doc.get("last_mod_by", "")
except Exception as e:
    st.error(f"Node offline: {e}")
    st.stop()

# ── 5. Toolbar ──
st.markdown(
    f"""
<div class="toolbar">
    <div class="left">
        <span class="doc-icon">📄</span>
        <span class="room-name">{current_topic}</span>
        <span class="node-badge">{node_id}</span>
    </div>
    <div class="right">
        <span class="version-pill">v{version}</span>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# ── 6. Document Page ──
new_content = st.text_area(
    "document_editor",
    value=content,
    height=400,
    placeholder="Start typing your document here...",
    label_visibility="collapsed",
)

if st.button("💾 Save", use_container_width=True):
    requests.post(
        f"http://127.0.0.1:{target_port}/edit",
        json={"document": {"content": new_content}},
    )
    st.rerun()

# ── 7. Footer Metadata ──
last_mod_display = f"...{last_mod[-12:]}" if len(last_mod) > 12 else (last_mod or "—")
st.markdown(
    f"""
<div class="doc-footer">
    <span>Last edited by: {last_mod_display}</span>
    <span>Version {version}</span>
</div>
""",
    unsafe_allow_html=True,
)
