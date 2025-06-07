from typing import TypedDict, List

from langchain.docstore.document import Document


class AgentState(TypedDict):
    # The input string
    query: str
    # The list of previous messages in the conversation
    messages: str

    documents: List[Document]

    files: List[str]
    # The outcome of a given call to the agent
    # Needs `None` as a valid type, since this is what this will start as
