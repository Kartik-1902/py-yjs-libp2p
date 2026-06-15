from libp2p.utils import logging
import json
import logging
import os
from pathlib import Path
from typing import Any, Callable, Awaitable

import trio
from multiaddr import Multiaddr

from libp2p import new_host
from libp2p.crypto.ed25519 import create_new_key_pair  # <-- Notice we use ed25519 here!
from libp2p.peer.id import ID
from libp2p.peer.peerinfo import PeerInfo, info_from_p2p_addr
from libp2p.pubsub.gossipsub import GossipSub
from libp2p.pubsub.pubsub import Pubsub

# We'll need these imports later for Phase 4 (mDNS discovery), 
# but you can add them now if you want to prep the file:
from libp2p.discovery.events.peerDiscovery import peerDiscovery
from libp2p.discovery.mdns.mdns import MDNSDiscovery

logger = logging.getLogger(__name__)

def load_create_key(node_id: str):
    key_file = Path("keys") / f"{node_id}.json"
    key_file.parent.mkdir(parents = True, exist_ok= True)

    #loading private key file
    if key_file.exists():
        try:
            with open (key_file , 'r') as f:
                data = json.load(f)
            secret = bytes.fromhex(data['private_key'])
            return create_new_key_pair(secret)
        except Exception as e:
            logger.error(f"failed to load private key for {node_id}: {e}")
    # generating new key_pair 
    logger.info("generating new key")
    key_pair = create_new_key_pair()
    with open (key_file,'w') as f:
        json.dump({"private_key": key_pair.private_key.to_bytes().hex()}, f)
    
    return key_pair

class p2pNode():
    def __init__(
        self , 
        node_id: str, 
        p2p_port: int
        ):
        self.node_id = node_id
        self.p2p_port = p2p_port

        self.host: Any = None
        self.peer_id_str: str =""

    async def setup(self) -> None: 
        key_pair = load_create_key(self.node_id)
        listen_addr = [Multiaddr(f"/ip4/0.0.0.0/tcp/{self.p2p_port}")]
        self.host = new_host(key_pair = key_pair, listen_addrs=listen_addr )
        self.peer_id_str = str(self.host.get_id())

    async def connect_to_peer(self, multiaddr_str: str) -> ID:
        try:
            info = info_from_p2p_addr(Multiaddr(multiaddr_str))
            await self.host.connect(info)
            logger.info(f"Connected to {info.peer_id}")
            return info.peer_id
        except Exception as e: 
            logger.error(f"Failed to connect {multiaddr_str}: {e}")