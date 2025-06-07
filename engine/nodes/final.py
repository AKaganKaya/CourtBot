from nodes.state import AgentState
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain

# 3. Node for Generating the Final Answer with Streaming
class FinalAnswerNode:
    def __init__(self):
        super().__init__()
        self.llm = ChatOpenAI(model="gpt-4o")  # Enable streaming
 
    def __call__(self, state: AgentState):
        document_text = "\n".join(state["documents"])
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "Sen Veridictum isimli Türk hukuku yargıtay kararları üzerine bir uzmansın. Görevin sana sorulan soruya verilen yargıtay kararları sayesinde cevaplamaktır.",
                ),
                (
                    "human",
                    f"Yargıtay kararları aşağıdaki gibi verilmiştir:\n{document_text}\nSana verilen yargıtay kararlarına göre aşağıdaki soruyu cevaplar mısın? Soruyu cevaplarken sana verilen kararlardan referans cümleler vermeyi unutma. Referans verdiğin yargıtay kararlarının karar ve emsal numaralarını da ver. Eğer yargıtay kararı verilmemişse kısace bu soruya cevap veremeyeceğini söyle. Soru şu şekildedir:\n{{query}}."
                ),
            ]
        )

        chain = LLMChain(prompt=prompt, llm=self.llm)
        
        # Invoke the LLM with a callback to handle streaming
        final_answer = chain.invoke(
            {
                "query": state["query"],
            }
        )

        return {"messages": final_answer["text"]}
