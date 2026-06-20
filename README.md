# Py-Yjs-Libp2p 🌐

A local-only, multi-process Python implementation of CRDT (Conflict-free Replicated Data Type) synchronization over a true Peer-to-Peer network.

This project demonstrates how to build a decentralized, real-time document synchronization engine (similar to Google Docs or Figma) using Py-Libp2p without any central servers.

## 🏗️ Architecture

The network is completely decentralized and relies on the following core components:

1. **mDNS (Zero-Configuration Discovery):** Nodes automatically discover and connect to each other on the local Wi-Fi/LAN network without needing hardcoded IP addresses.
1. **GossipSub (Real-Time Broadcasting):** When a document is edited, the edit is broadcasted to the entire network mesh in milliseconds.
1. **Stream Sync (Late Joiner Reconciliation):** If a new node joins the network after edits have already been made, it opens a direct 1-on-1 TCP stream to an existing peer to download the full document state.
1. **CRDT State Management:** Edits are reconciled using a Last-Write-Wins (LWW) mechanism based on Document Versions to ensure mathematically idempotent updates regardless of network delays or race conditions.
1. **Trio Async Loop:** High-performance asynchronous execution bridging the Libp2p network layer with the HTTP API layer.
1. **Streamlit UI:** A decoupled, real-time Web Dashboard that acts as a visual "Control Panel" to monitor the underlying P2P network.

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (Extremely fast Python package manager)

### Installation

Ensure you have `uv` installed, then simply clone the repository and sync the environment:

```bash
uv sync
```

This will automatically install all dependencies, including the strictly version-pinned `py-libp2p` and tools like Streamlit.

### Running the Network & UI

We have included a network launcher that automatically spins up 3 background nodes (Node 0, Node 1, and Node 2).

1. Start the Network Launcher:

```bash
uv run python launcher/spawn_network.py
```

*Leave this terminal open. Press `Ctrl+C` to gracefully shut down all 3 nodes at once.*

2. Open a **new terminal tab** and launch the Streamlit Google Docs UI:

```bash
uv run streamlit run ui/local_node.py
```

3. A web browser will open at `http://localhost:8501`. 
   - Open multiple tabs in your browser. Each tab will automatically claim a free node (Node 0, Node 1, etc.) using heartbeat leases.
   - You can use the left sidebar to switch rooms (topics). 
   - Nodes in the same room will sync their state instantly via GossipSub, while nodes in different rooms remain securely isolated!

## 🛠️ Manual Node Execution

If you prefer to start nodes manually to observe their terminal outputs:

**Start Node A:**

```bash
uv run python -m node.main --node-id NodeA --api-port 8000 --p2p-port 9000
```

**Start Node B:**

```bash
uv run python -m node.main --node-id NodeB --api-port 8001 --p2p-port 9001
```

Within 3-5 seconds, Node A and Node B will automatically discover each other via mDNS and sync their states.

### Interacting via API

You can interact with the nodes using any HTTP client (like `curl` or PowerShell `Invoke-RestMethod`):

**Check State:**

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/state
```

**Change Room:**

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/topic -Method POST -Body '{"topic":"Secret-Room"}' -ContentType "application/json"
```

**Edit Document:**

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/edit -Method POST -Body '{"document":{"content":"Hello P2P World!"}}' -ContentType "application/json"
```

## 📋 Project Status

- [x] Phase 1: Core P2P Node & Trio Nursery Integration
- [x] Phase 2: CRDT State Data Structures & HTTP API
- [x] Phase 3: GossipSub Radio & Stream Sync (Late Joiner Problem)
- [x] Phase 4: mDNS Local Network Discovery
- [x] Phase 5: Automated Network Launcher
- [x] Phase 6: Dynamic Room/Topic Switching & Google Docs UI
