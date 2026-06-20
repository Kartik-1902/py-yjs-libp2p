from libp2p.custom_types import TProtocol

# --- Ports ---
DEFAULT_P2P_PORT = 9000
DEFAULT_API_PORT = 8000

GOSSIPSUB_ID = TProtocol("/meshsub/1.0.0")
TOPIC_PREFIX = "/py-yjs-libp2p/sheet/"
# --- GossipSub Parameters ---
# (Standard tuning values for a fast local network)
GOSSIPSUB_DEGREE = 6
GOSSIPSUB_DEGREE_LOW = 4
GOSSIPSUB_DEGREE_HIGH = 8
GOSSIPSUB_HEARTBEAT_INTERVAL = 1
GOSSIPSUB_HEARTBEAT_INITIAL_DELAY = 0.5
GOSSIPSUB_TIME_TO_LIVE = 60
GOSSIPSUB_GOSSIP_WINDOW = 3
GOSSIPSUB_GOSSIP_HISTORY = 5

# -------------MDNS----------------
MDNS_ENABLED_DEFAULT = True

# --- Stream protocol for state sync ---
SYNC_PROTOCOL_ID = TProtocol("/py-yjs-libp2p/sync/1.0.0")
