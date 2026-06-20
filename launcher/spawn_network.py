import subprocess
import json
import time
import sys

processes= []
registry = {"nodes":[]}
try:
    for i in range(3):
        api_port = 8000+i
        p2p_port = 9000+i

        cmd = ["uv", "run","python", "-m", "node.main", "--node-id", f"Node{i}", "--api-port", str(api_port), "--p2p-port", str(p2p_port) ]
        p= subprocess.Popen(cmd)
        processes.append(p)
        registry["nodes"].append({
            "id": f"Node{i}",
            "api_port": api_port,
            "p2p_port": p2p_port
        })
    with open ("network_registry.json" , 'w') as f:
        json.dump(registry,f ,indent=4)
    print(f"network is running! Press Ctrl+C to stoll all nodes")
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nStopping Network...")
    for p in processes:
        p.terminate()