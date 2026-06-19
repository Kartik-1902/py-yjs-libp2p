from anyio import sleep
from libp2p import pubsub
from httpcore import __name
import argparse
import argparse
import logging
import trio
from multiaddr import Multiaddr
from hypercorn.config import Config
from hypercorn.trio import serve
from libp2p.tools.anyio_service import background_trio_service


from .config import DEFAULT_API_PORT, DEFAULT_P2P_PORT
from .state import SharedDocument
from .server import create_api_app 
from .p2p_node import p2pNode 


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run(args):
    state = SharedDocument()

    p2p = p2pNode(node_id=args.node_id , p2p_port=args.p2p_port, state=state )
    await p2p.setup()

    app = create_api_app(p2p ,state)

    hc_config = Config()
    hc_config.bind = [f"0.0.0.0:{args.api_port}"]
    hc_config.accesslog = None #silent

    print(f"\n--- Node {args.node_id} ---")
    print(f"Peer ID: {p2p.peer_id_str}")
    print(f"API Server listening on http://localhost:{args.api_port}/state\n")

    from multiaddr import Multiaddr
    listen_addrs = [Multiaddr(f"/ip4/0.0.0.0/tcp/{args.p2p_port}")]

    try: 
        async with p2p.host.run(listen_addrs=listen_addrs):
            print(f"P2P Addr: {p2p.host.get_addrs()}")
            

            async with background_trio_service(p2p.pubsub):
                async with background_trio_service(p2p.gossipsub):
                    
                    token = trio.lowlevel.current_trio_token()
                    p2p.start_mdns(token)
                    async with trio.open_nursery() as nursery:
                        # start web server
                        nursery.start_soon(serve,app, hc_config)
                        nursery.start_soon(p2p.read_message, "default-topic",state)
                        nursery.start_soon(p2p.mdns_consumer)
                        if args.connect:
                            peer_id=await p2p.connect_to_peer(args.connect)
                            nursery.start_soon(p2p._request_sync, peer_id)
    finally:
        logger.info("shutdown gracefully...")
        await p2p.host.close()
    
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--node-id", required=True, type=str, help="e.g NodeA")
    parser.add_argument("--api-port", default=DEFAULT_API_PORT, type=int)
    parser.add_argument("--p2p-port", default=DEFAULT_P2P_PORT, type= int)
    parser.add_argument("--connect", type=str, help="e.g /ipv4/0.0.0.0/tcp/9000/p2p/Qm.....")
    args = parser.parse_args()
    trio.run(run,args)
if __name__ == "__main__":
    main()