import os
import asyncio
import websockets
import json
import faiss
import pickle
from langgraph.graph import StateGraph, END, START
from nodes.final import FinalAnswerNode
from nodes.search import SearchEngineNode
from nodes.state import AgentState
import chainlit as cl


# Initialize OpenAI API
os.environ["OPENAI_API_KEY"] = "sk-k1IIz-43DMa1e3ZfBFadTKYwKtQR0mSoekmYN7oP5uT3BlbkFJoERIX7i4SmX6zRiDOBaFyMb4olYKj6uJwglIkoFXMA"
faiss_path = "database/faiss.index"
metadata_path = "database/metadata.pkl"
index = faiss.read_index(str(faiss_path))
with open(metadata_path, "rb") as f:
    metadata = pickle.load(f)

# Initialize nodes for workflow
search_node = SearchEngineNode(index, metadata)
final_node = FinalAnswerNode()

# Create the workflow graph
workflow = StateGraph(AgentState)

# Add nodes to the graph
workflow.add_node("search", search_node)
workflow.add_node("answer", final_node)

# Define the edges between nodes
workflow.add_edge(START, "search")
workflow.add_edge("search", "answer")
workflow.add_edge("answer", END)

# Set the entry point of the graph
app = workflow.compile()

async def handle_message(websocket, message):
    try:
        # Prepare inputs for the workflow
        inputs = {"query": message, "messages": None, "documents": [], "files": []}
        
        # Invoke the workflow
        result = app.invoke(inputs)

        # Extract the output messages
        output = result["messages"]

        # Send back the response to the client
        await websocket.send(output)

    except Exception as e:
        print(f"Error: {e}", flush=True)
        await websocket.send(json.dumps({"error": str(e)}))

async def websocket_server(websocket):
    try:
        async for message in websocket:
            print("Received message:", message, flush=True)
            # Process the received message
            await handle_message(websocket, message)
    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected", flush=True)
    except Exception as e:
        print(f"Error: {e}", flush=True)

async def main():
    print("WebSocket server starting", flush=True)
    
    # Create the WebSocket server
    async with websockets.serve(websocket_server, "0.0.0.0", 8090):
        print("WebSocket server running on port 8090", flush=True)
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
