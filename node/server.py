from starlette.applications import Starlette 
from starlette.routing import Route
from starlette.responses import JSONResponse

def create_api_app(p2p_node, state):
    async def get_state(request):
        return JSONResponse({
            "peer_id": p2p_node.peer_id_str,
            "document": state.to_dict(),
            "connected_to": [str(peer) for peer in p2p_node.host.get_network().connections.keys()]
        })
    
    return Starlette(routes=[Route("/state", endpoint=get_state, methods=["GET"] )])