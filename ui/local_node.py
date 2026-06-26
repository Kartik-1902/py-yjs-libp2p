import sys
from pathlib import Path

# Allow importing from the node package when running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import requests
import json
import time
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from node.formula import evaluate_all_cells

COLUMNS = ["A", "B", "C", "D", "E"]
ROWS = 10

st.set_page_config(page_title="P2P Spreadsheet", layout="wide", initial_sidebar_state="collapsed")

# ── Custom CSS: Excel-inspired spreadsheet ──
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

.stApp {
    font-family: 'Inter', sans-serif;
}
header[data-testid="stHeader"] { background: transparent; }
.block-container {
    max-width: 960px;
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

/* ── Spreadsheet grid styling ── */
div[data-testid="stDataFrame"] table {
    font-family: 'Inter', monospace !important;
    font-size: 14px !important;
}

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


# ── 2. Node Assignment via URL query params & Leases ──
@st.cache_resource
def get_node_leases():
    return {}  # { node_id: last_seen_timestamp }


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
    cells = doc.get("content", {})  # {"A1": "hello", "B3": "42", ...}
    if not isinstance(cells, dict):
        cells = {}  # Handle old-format string content from unrestarted nodes
    last_mod = doc.get("last_mod_by", "")
except Exception as e:
    st.error(f"Node offline: {e}")
    st.stop()

# ── 5. Toolbar ──
st.markdown(
    f"""
<div class="toolbar">
    <div class="left">
        <span class="doc-icon">📊</span>
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


# ── 6. Spreadsheet Grid ──
def cells_to_dataframe(cells_dict: dict) -> pd.DataFrame:
    """Convert a flat cell dict like {"A1": "hello"} into a 10x5 DataFrame."""
    data = {col: [""] * ROWS for col in COLUMNS}
    for cell_key, value in cells_dict.items():
        if len(cell_key) < 2:
            continue
        col_letter = cell_key[0].upper()
        try:
            row_num = int(cell_key[1:])
        except ValueError:
            continue
        if col_letter in COLUMNS and 1 <= row_num <= ROWS:
            data[col_letter][row_num - 1] = str(value)
    df = pd.DataFrame(data)
    df.index = list(range(1, ROWS + 1))
    return df


def dataframe_to_cells(df: pd.DataFrame) -> dict:
    """Convert a DataFrame back to a flat cell dict."""
    cells_out = {}
    for col in COLUMNS:
        for row_idx in range(ROWS):
            val = str(df.at[row_idx + 1, col]) if df.at[row_idx + 1, col] is not None else ""
            cell_key = f"{col}{row_idx + 1}"
            cells_out[cell_key] = val
    return cells_out


def diff_cells(original: dict, edited: dict) -> dict:
    """Return only the cells that changed between original and edited."""
    changed = {}
    for key, val in edited.items():
        if original.get(key, "") != val:
            changed[key] = val
    return changed


# ── 6a. Auto-save pending edits from previous refresh cycle ──
# Streamlit stores data_editor edits in session_state["spreadsheet"]
# We must push them to the backend BEFORE rebuilding the grid,
# so the next fetch picks them up and they don't vanish.
if "spreadsheet" in st.session_state:
    editor_state = st.session_state["spreadsheet"]
    edited_rows = editor_state.get("edited_rows", {})
    if edited_rows:
        changed_cells = {}
        for row_idx_str, col_changes in edited_rows.items():
            row_num = int(row_idx_str) + 1  # data_editor uses 0-indexed rows
            for col_letter, new_val in col_changes.items():
                cell_key = f"{col_letter}{row_num}"
                changed_cells[cell_key] = str(new_val) if new_val is not None else ""
        # Filter out cells whose value already matches the backend to prevent
        # infinite save loops caused by Streamlit type mismatches (e.g. int 5
        # vs string "5" in edited_rows that never clears).
        new_changes = {k: v for k, v in changed_cells.items() if cells.get(k, "") != v}
        if new_changes:
            requests.post(
                f"http://127.0.0.1:{target_port}/edit",
                json={"document": {"content": new_changes}},
            )
            # Re-fetch state after saving so the grid shows the saved values
            response = requests.get(f"http://127.0.0.1:{target_port}/state", timeout=2)
            raw_json = response.json()
            doc = raw_json.get("document", {})
            version = doc.get("version", 0)
            cells = doc.get("content", {})
            if not isinstance(cells, dict):
                cells = {}


# Evaluate formulas and build the grid from computed state
computed_cells = evaluate_all_cells(cells)
original_df = cells_to_dataframe(computed_cells)

# ── 6b. Formula Bar ──
st.markdown("##### 🔍 Formula Bar")
col_sel, row_sel, formula_input = st.columns([1, 1, 6])
with col_sel:
    selected_col = st.selectbox("Col", COLUMNS, index=0, label_visibility="collapsed")
with row_sel:
    selected_row = st.selectbox("Row", list(range(1, ROWS + 1)), index=0, label_visibility="collapsed")

selected_cell = f"{selected_col}{selected_row}"
current_raw_value = cells.get(selected_cell, "")

# Sync the formula bar's session state with the backend.
# st.text_input ignores the `value` param after the first render and uses
# session state instead.  When the backend value changes externally (grid
# auto-save, peer sync), we must update the session state so the formula
# bar doesn't overwrite the new value with its stale cached text.
formula_key = f"formula_{selected_cell}"
backend_key = f"_backend_{selected_cell}"
if st.session_state.get(backend_key) != current_raw_value:
    st.session_state[formula_key] = current_raw_value
    st.session_state[backend_key] = current_raw_value

with formula_input:
    new_formula = st.text_input(
        f"Formula/Value for {selected_cell}",
        value=current_raw_value,
        placeholder="Enter value or formula (e.g., =A1+B2)",
        label_visibility="collapsed",
        key=formula_key,
    )

if new_formula != current_raw_value:
    requests.post(
        f"http://127.0.0.1:{target_port}/edit",
        json={"document": {"content": {selected_cell: new_formula}}},
    )
    # Update the backend tracker so next rerun doesn't revert the change
    st.session_state[backend_key] = new_formula
    st.rerun()

st.markdown("##### ✏️ Edit Cells (enter formulas with `=`, e.g. `=A1+B2`)")
st.caption("💡 Edits auto-save every second")
edited_df = st.data_editor(
    original_df,
    use_container_width=True,
    num_rows="fixed",
    key="spreadsheet",
)

# ── 8. Footer Metadata ──
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
