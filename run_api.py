import websocket
import uuid
import json
import urllib.request
import urllib.parse
import os
import argparse
import base64
import requests
import time
import random # Import the random library

from fastapi import FastAPI, Form, File, UploadFile
from fastapi.responses import JSONResponse
import uvicorn
from typing import Optional, Union, Dict, Any

# --- Global Variables ---
server_address = "127.0.0.1:8188"
client_id = str(uuid.uuid4())
workflow_api_json = {}
VERBOSE = False

# --- ComfyUI Interaction Logic ---

def find_node_id(workflow: Dict[str, Any], node_title: Optional[str] = None, node_type: Optional[str] = None) -> Optional[str]:
    """Finds a node's ID by its title or class_type."""
    for node_id, node_data in workflow.items():
        if isinstance(node_data, dict):
            if node_title and node_data.get("_meta", {}).get("title") == node_title:
                return node_id
            if node_type and node_data.get("class_type") == node_type:
                return node_id
    return None

def queue_prompt(prompt_workflow: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    # ... (function is unchanged)
    try:
        p = {"prompt": prompt_workflow, "client_id": client_id}
        data = json.dumps(p).encode('utf-8')
        req = urllib.request.Request(f"http://{server_address}/prompt", data=data)
        response = urllib.request.urlopen(req)
        return json.loads(response.read())
    except Exception as e:
        print(f"Error queuing prompt: {e}")
        return None

def get_history(prompt_id: str) -> Dict[str, Any]:
    # ... (function is unchanged)
    try:
        with urllib.request.urlopen(f"http://{server_address}/history/{prompt_id}") as response:
            return json.loads(response.read())
    except Exception as e:
        print(f"Error fetching history: {e}")
        return {}

def parse_video_path_from_output(outputs: Dict[str, Any]) -> Optional[str]:
    # ... (function is unchanged)
    if "text" not in outputs or not isinstance(outputs["text"], list) or not outputs["text"]:
        return None
    stringified_list = outputs["text"][0]
    try:
        parsed_list = json.loads(stringified_list)
        if isinstance(parsed_list, list) and len(parsed_list) > 1:
            path_list = parsed_list[1]
            if isinstance(path_list, list):
                for path in path_list:
                    if isinstance(path, str) and path.endswith(('.mp4', '.webm', '.avi', '.mov')):
                        return path
    except Exception:
        return None
    return None

def get_final_video_path(prompt_id: str, target_node_id: str) -> Optional[str]:
    # ... (function is unchanged)
    ws = websocket.WebSocket()
    try:
        if VERBOSE: print("Connecting to WebSocket to monitor target node...")
        ws.connect(f"ws://{server_address}/ws?clientId={client_id}")
        ws.settimeout(300)
        while True:
            out = ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if VERBOSE: print(f"RECEIVED WS MESSAGE: {json.dumps(message, indent=2)}")
                if message.get('type') == 'executed' and message.get('data', {}).get('node') == target_node_id:
                    if VERBOSE: print(f"SUCCESS: Found executed message for target node {target_node_id}.")
                    outputs = message.get('data', {}).get('output', {})
                    return parse_video_path_from_output(outputs)
    except websocket.WebSocketTimeoutException:
        print("ERROR: WebSocket timed out.")
    except Exception as e:
        print(f"Error in websocket communication: {e}")
    finally:
        if ws.connected: ws.close()
    print("WebSocket failed. Falling back to history...")
    time.sleep(1)
    history = get_history(prompt_id).get(prompt_id, {})
    if history and target_node_id in history.get('outputs', {}):
        return parse_video_path_from_output(history['outputs'][target_node_id])
    return None

def upload_image(image_data: Union[UploadFile, str]) -> str:
    # ... (function is unchanged)
    if isinstance(image_data, str):
        img_bytes = base64.b64decode(image_data)
        files = {'image': ("image.png", img_bytes, 'image/png')}
    else:
        files = {'image': (image_data.filename, image_data.file.read(), image_data.content_type)}
    data = {"overwrite": "true"}
    response = requests.post(f"http://{server_address}/upload/image", files=files, data=data)
    response.raise_for_status()
    return response.json()['name']

# --- FastAPI Application ---
app = FastAPI()

@app.post("/generate-video")
async def generate_video(
    image: Union[UploadFile, str] = Form(...),
    prompt: str = Form(...),
    negative_prompt: Optional[str] = Form(""),
):
    try:
        prompt_workflow = json.loads(json.dumps(workflow_api_json))

        image_node_id = find_node_id(prompt_workflow, node_title="load_image")
        pos_prompt_node_id = find_node_id(prompt_workflow, node_title="positive_prompt")
        neg_prompt_node_id = find_node_id(prompt_workflow, node_title="negative_prompt")
        output_node_id = find_node_id(prompt_workflow, node_title="output_paths")
        k_sampler_node_id = find_node_id(prompt_workflow, node_type="KSampler") # Find the KSampler

        if not all([image_node_id, pos_prompt_node_id, neg_prompt_node_id, output_node_id]):
            # ... (error handling remains the same)
            missing = [title for title, node_id in [("load_image", image_node_id), ("positive_prompt", pos_prompt_node_id), ("negative_prompt", neg_prompt_node_id), ("output_paths", output_node_id)] if not node_id]
            return JSONResponse(status_code=404, content={"error": f"Could not find required nodes. Missing titles: {', '.join(missing)}"})

        # Modify the workflow inputs
        image_filename = upload_image(image)
        prompt_workflow[image_node_id]["inputs"]["image"] = image_filename
        prompt_workflow[pos_prompt_node_id]["inputs"]["text"] = prompt
        prompt_workflow[neg_prompt_node_id]["inputs"]["text"] = negative_prompt

        # --- THIS IS THE NEW, CRITICAL PART ---
        if k_sampler_node_id:
            # Generate a new random seed to ensure the workflow runs fresh every time
            random_seed = random.randint(0, 999999999999999)
            prompt_workflow[k_sampler_node_id]["inputs"]["seed"] = random_seed
            if VERBOSE:
                print(f"Randomized KSampler seed (node {k_sampler_node_id}) to: {random_seed}")
        else:
            if VERBOSE:
                print("Warning: KSampler node not found. Seed will not be randomized, which may cause caching issues.")
        # ------------------------------------

        # Queue the prompt and get the result
        queued_item = queue_prompt(prompt_workflow)
        if not queued_item or 'prompt_id' not in queued_item:
            return JSONResponse(status_code=500, content={"error": "Failed to queue prompt in ComfyUI."})

        prompt_id = queued_item['prompt_id']
        video_path = get_final_video_path(prompt_id, output_node_id)

        if not video_path:
            return JSONResponse(status_code=500, content={"error": "Generation finished, but failed to extract video path. Run with --verbose for details."})
        
        return JSONResponse(content={"generated_video_path": video_path})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

def main():
    global server_address, workflow_api_json, VERBOSE

    parser = argparse.ArgumentParser(description="A robust FastAPI wrapper for ComfyUI video generation.")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the FastAPI server to.")
    parser.add_argument("--port", type=int, default=8000, help="Port to run the FastAPI server on.")
    parser.add_argument("--comfyui-url", type=str, default="127.0.0.1:8188", help="The URL of the ComfyUI server.")
    parser.add_argument("--workflow", type=str, required=True, help="Path to the ComfyUI API Format workflow JSON file.")
    parser.add_argument("--verbose", action="store_true", help="Enable detailed verbose logging for debugging.")

    args = parser.parse_args()

    server_address = args.comfyui_url
    VERBOSE = args.verbose
    
    if not os.path.isfile(args.workflow):
        print(f"Error: Workflow file not found at {args.workflow}")
        return
        
    print("Loading API format workflow from:", args.workflow)
    with open(args.workflow, 'r', encoding='utf-8') as f:
        workflow_api_json = json.load(f)
    print("Workflow loaded successfully.")
    
    print(f"Starting FastAPI server on {args.host}:{args.port}")
    print("Mode: Targeting 'output_paths' node for result. KSampler seed will be randomized on each request.")
    if VERBOSE:
        print("--- VERBOSE LOGGING IS ON ---")
        
    uvicorn.run(app, host=args.host, port=args.port)

if __name__ == "__main__":
    main()