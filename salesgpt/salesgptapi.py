import json
from langchain.chat_models import ChatLiteLLM
from salesgpt.agents import SalesGPT
import faiss
from salesgpt.tools import setup_knowledge_base, get_tools

GPT_MODEL = "gpt-4-1106-preview"

class SalesGPTAPI:
    USE_TOOLS = True  # Set to True if using tools
    FAISS_INDEX_PATH = "salesgpt/embeddings.index"  # Path to the FAISS index

    def __init__(self, config_path: str, verbose: bool = False, max_num_turns: int = 100):
        print("vwgwgagagagaegagae")
        self.config_path = config_path
        self.verbose = verbose
        self.max_num_turns = max_num_turns
        self.llm = ChatLiteLLM(temperature=0.2, model_name=GPT_MODEL)
        if self.USE_TOOLS:
            # Initialize FAISS index and embeddings model for the battery search tool
            print("wfwef")
            self.faiss_index, self.embeddings_model = setup_knowledge_base(self.FAISS_INDEX_PATH)
            print("wv")
            self.tools = get_tools(self.faiss_index, self.embeddings_model)
        else:
            self.tools = None

    def do(self, conversation_history: [str], human_input=None):
        if self.config_path == "":
            print("No agent config specified, using a standard config")
            sales_agent = SalesGPT.from_llm(
                self.llm,
                use_tools=self.USE_TOOLS,
                tools=self.tools,
                salesperson_name="Ted Lasso",
                verbose=self.verbose,
            )
        else:
            with open(self.config_path, "r") as f:
                config = json.load(f)
            if self.verbose:
                print(f"Agent config {config}")
            sales_agent = SalesGPT.from_llm(self.llm, verbose=self.verbose, tools=self.tools, **config)

        current_turns = len(conversation_history) + 1
        if current_turns >= self.max_num_turns:
            print("Maximum number of turns reached - ending the conversation.")
            return {"name": "Agent", "reply": "<END_OF_CALL>"}

        sales_agent.seed_agent()
        sales_agent.conversation_history = conversation_history

        if human_input is not None:
            sales_agent.human_step(human_input)

        sales_agent.step()

        if "<END_OF_CALL>" in sales_agent.conversation_history[-1]:
            print("Sales Agent determined it is time to end the conversation.")
            return "<END_OF_CALL>"

        reply = sales_agent.conversation_history[-1]

        if self.verbose:
            print("=" * 10)
            print(f"{sales_agent.salesperson_name}:{reply}")
        return {"name": sales_agent.salesperson_name, "reply": reply}
