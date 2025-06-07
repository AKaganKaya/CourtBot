import os
from langgraph.graph import StateGraph, END, START
from nodes.final import FinalAnswerNode
from nodes.search import SearchEngineNode
from nodes.state import AgentState
import chainlit as cl
import faiss
import pickle

    
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

while True:
    message = input("Enter the query!\n")
    inputs = {"query": message, "messages": None, "documents": [], "files":[]}
    
    # Invoke the workflow
    result = app.invoke(inputs)

    output = result["messages"]

    # Return the final result
    print("-----------------------------------")
    print(output)
    print("-----------------------------------")

