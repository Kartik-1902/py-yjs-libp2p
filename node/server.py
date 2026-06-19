from node.state import DocumentUpdate
from time import time
from starlette.applications import Starlette 
from starlette.routing import Route
import json
from starlette.responses import JSONResponse

def create_api_app(p2p_node, state):
    async def get_state(request):
        return JSONResponse({
            "peer_id": p2p_node.peer_id_str,
            "document": state.to_dict(),
            "connected_to": [str(peer) for peer in p2p_node.host.get_network().connections.keys()]
        })

    async def debug_broadcast(request) :
        json_data = await request.json()
        topic = json_data.get("topic" , "default-topic")
        msg = json_data.get("data", "hello network")

        msg_bytes = msg.encode("utf-8")
        await p2p_node.publish(topic, msg_bytes)

        return JSONResponse({
            "status" : "Broadcast sent"
        })

    async def edit_document(request):
        json_data = await request.json()
        new_doc = json_data.get("document",{})
        new_content = new_doc.get("content", "")

        state.content = new_content
        state.version +=1
        state.last_mod_by = p2p_node.peer_id_str
        state.last_updated_at = time()

        updated_msg = DocumentUpdate(
            content = state.content,
            version = state.version,
            last_mod_by = state.last_mod_by,
            last_updated_at = state.last_updated_at
        )

        await p2p_node.publish( "default-topic" , updated_msg.serialize())
        return JSONResponse({
            "status": "edit done locally",
            "new state": state.to_dict(),
        })
        
        
    
    return Starlette(routes=[Route("/state", endpoint=get_state, methods=["GET"] ), Route("/debug/broadcast", endpoint=debug_broadcast, methods=["POST"]), Route("/edit", endpoint=edit_document, methods=["POST"])])
