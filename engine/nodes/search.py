from nodes.state import AgentState
from search_engine.vector_database import search_faiss
import os
from search_engine.sentence import *

import difflib

import re

def transform_string(input_string):
    # Split the input string by underscores
    parts = input_string.split("_")
    
    # Capitalize each word in the first part (before the first underscore)
    first_part = parts[0]
    
    # Split into components (e.g., "9HukukDairesi" -> ['9', 'Hukuk', 'Dairesi'])
    components = re.findall(r'[A-Za-z]+|\d+', first_part)
    
    # Capitalize first letter of each component and join them back
    formatted_first_part = '. '.join([component.capitalize() for component in components])
    
    # Rebuild the string with the formatted first part
    transformed_string = formatted_first_part + ", " + ", ".join(parts[1:])
    
    return transformed_string


def find_concatenate_similar(string, string_list):
    # Find the most similar element with at least 90% similarity
    matcher = difflib.get_close_matches(string, string_list, n=1, cutoff=0.9)
    
    if not matcher:
        return None
    
    matched_string = matcher[0]
    index = string_list.index(matched_string)
    
    # Concatenate the previous, matched, and next elements if available
    previous_string = string_list[index - 1] if index > 0 else ""
    next_string = string_list[index + 1] if index < len(string_list) - 1 else ""
    
    concatenated_string = previous_string + ". " + matched_string + ". " +  next_string
    
    return concatenated_string

# 1. Node for BM25-based Search Engine API Query
class SearchEngineNode:
    def __init__(self, index, metadata):
        super().__init__()
        self.index = index
        self.metadata = metadata

    def __call__(self, state : AgentState):
        # Make a request to the BM25 search API
        retrieved_list = []
        files = []
        results = search_faiss(state["query"], self.index, self.metadata, top_k=10)
        for result in results:
            with open(os.path.join("courts", result["file"]), "r", encoding="utf-8") as f:
                body = extract_main_body(f.read())
                body = clean_text(body)
                sentences = custom_sentence_tokenize(body)
                sentences = merge_short_sentences(sentences)
                retrieved_list.append(transform_string(result["file"]) + "\n"+ find_concatenate_similar(result["sentence"], sentences))


            files.append(result["file"])

        return {"documents": retrieved_list, "files": files}
    
    


