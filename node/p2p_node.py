from hypercorn import trio
from node.config import MDNS_ENABLED_DEFAULT
from importlib.metadata import version
from node.config import SYNC_PROTOCOL_ID
from node.state import SharedDocument
from node.config import TOPIC_PREFIX
from node.config import GOSSIPSUB_GOSSIP_HISTORY
from node.config import GOSSIPSUB_GOSSIP_WINDOW
from node.config import GOSSIPSUB_TIME_TO_LIVE
from node.config import GOSSIPSUB_HEARTBEAT_INITIAL_DELAY
from node.config import GOSSIPSUB_HEARTBEAT_INTERVAL
from node.config import GOSSIPSUB_DEGREE_HIGH
from node.config import GOSSIPSUB_DEGREE_LOW
from node.config import GOSSIPSUB_DEGREE
from node.config import GOSSIPSUB_ID
from node.state import DocumentUpdate
from multiaddr import Multiaddr
from multiaddr import protocols
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
        p2p_port: int,
        state: SharedDocument,
        mdns_enabled: bool = MDNS_ENABLED_DEFAULT
        ):
        self.node_id = node_id
        self.p2p_port = p2p_port
        self.state = state
        self.mdns_enabled = mdns_enabled

        self.host: Any = None
        self.gossipsub: Any = None
        self.pubsub: Any = None
        self.subscription: dict[str, Any] = {}
        self.peer_id_str: str =""
        self._mdns_send : trio.MemorySendChannel[PeerInfo] | None = None
        self._mdns_recv: trio.MemoryReceiveChannel[PeerInfo] | None = None
        self._mdns : MDNSDiscovery | None = None

    async def setup(self) -> None: 
        key_pair = load_create_key(self.node_id)
        listen_addr = [Multiaddr(f"/ip4/0.0.0.0/tcp/{self.p2p_port}")]
        self.host = new_host(key_pair = key_pair, listen_addrs=listen_addr )
        self.peer_id_str = str(self.host.get_id())

        self.host.set_stream_handler(SYNC_PROTOCOL_ID,  self._handel_sync_request)

        #initializing gossipsub 
        self.gossipsub = GossipSub(
            protocols = [GOSSIPSUB_ID],
            degree = GOSSIPSUB_DEGREE,
            degree_low= GOSSIPSUB_DEGREE_LOW,
            degree_high= GOSSIPSUB_DEGREE_HIGH,
            heartbeat_interval= GOSSIPSUB_HEARTBEAT_INTERVAL,
            heartbeat_initial_delay= GOSSIPSUB_HEARTBEAT_INITIAL_DELAY,
            time_to_live= GOSSIPSUB_TIME_TO_LIVE,
            gossip_window= GOSSIPSUB_GOSSIP_WINDOW,
            gossip_history= GOSSIPSUB_GOSSIP_HISTORY
        )
        self.pubsub = Pubsub(
            self.host,
            self.gossipsub,
            strict_signing = False
        )

    async def _request_sync(self, peer_id: ID):
        stream = None
        try:
            stream = await self.host.new_stream(peer_id, [SYNC_PROTOCOL_ID])
            data = await stream.read(10*1024*1024)
            if data:
                state_dict = json.loads(data.decode("utf-8"))
                if state_dict["version"] > self.state.version:
                    self.state.content = state_dict["content"]
                    self.state.version = state_dict["version"]
                    self.state.last_mod_by = state_dict["last_mod_by"]
                    self.state.last_updated_at = state_dict["last_updated_at"]
                    logger.info(f"sync request succesfull")
        except Exception as e:
            logger.error(f"sync request faild: {e}")
        finally:
            if stream:
                await stream.close()

    def start_mdns(self, trio_token: trio.lowlevel.TrioToken)-> None:
        send , recv = trio.open_memory_channel(16)
        self._mdns_send = send
        self._mdns_recv= recv

        self._mdns = MDNSDiscovery(self.host.get_network(), self.p2p_port)

        def _on_discovered(peer_info):
            try:
                trio.from_thread.run_sync(self._mdns_send.send_nowait, peer_info, trio_token=trio_token)
            except (trio.WouldBlock, trio.ClosedResourceError):
                pass

        peerDiscovery.register_peer_discovered_handler(_on_discovered)
        self._mdns.start()
        logger.info("mDNS discovery started. Scanning Wi-Fi.....")

    async def mdns_consumer(self)-> None:
        if not self._mdns_recv:
            return 
        async for peer_info in self._mdns_recv:
            try:
                if self.host.get_id()!=peer_info.peer_id:
                    await self.host.connect(peer_info)
                logger.info(f"mDNS auto-connected to {peer_info.peer_id}")
                if self.state.version ==0:
                    await self._request_sync(peer_info.peer_id)
            except Exception:
                pass

    
    async def _handel_sync_request(self, stream) -> None:
        try:
            response_byte = json.dumps(self.state.to_dict()).encode("utf-8")
            await stream.write(response_byte)
            logger.info("stream write successful")
        except Exception as e:
            logger.error(f"sync failed, stream error : {e}")
        finally: 
            await stream.close()


    async def subscribe(self, sheet_topic: str) -> None:
        topic = f"{TOPIC_PREFIX}{sheet_topic}"
        subscription = await self.pubsub.subscribe(topic)
        self.subscription[sheet_topic] = subscription
        logger.info(f"Subscribed to topic: {topic}")

    async def read_message(self, sheet_topic:str, state)->None:
        await self.subscribe(sheet_topic)
        subscription = self.subscription.get(sheet_topic)

        if not subscription:
            return

        while True:
            try:
                message = await subscription.get()
                incoming_message= DocumentUpdate.deserialize(message.data)
                if incoming_message.version > state.version:
                    state.content = incoming_message.content
                    state.version = incoming_message.version
                    state.last_mod_by = incoming_message.last_mod_by
                    state.last_updated_at = incoming_message.last_updated_at
                    print(f"[GOSSIPSUB] updated state, New state: {state.version}")
                else: 
                    print(f"[GOSSIPSUB] ignored older state")
            except Exception as e:
                logger.error(f"Failed to read message: {e}")
        
    async def publish(self , topic:str, data: bytes):
        topic = f"{TOPIC_PREFIX}{topic}"
        await self.pubsub.publish(topic, data)

    async def connect_to_peer(self, multiaddr_str: str) -> ID:
        try:
            info = info_from_p2p_addr(Multiaddr(multiaddr_str))
            await self.host.connect(info)
            logger.info(f"Connected to {info.peer_id}")
            return info.peer_id
        except Exception as e: 
            logger.error(f"Failed to connect {multiaddr_str}: {e}")