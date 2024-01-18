import json
from langchain.chat_models import ChatLiteLLM
from salesgpt.agents import SalesGPT
import faiss
from salesgpt.tools import setup_knowledge_base, get_tools

GPT_MODEL = "gpt-4-1106-preview"
current_data_index = 0

class SalesGPTAPI:
    USE_TOOLS = True  # Set to True if using tools
    FAISS_INDEX_PATH = "salesgpt/embeddings.index"  # Path to the FAISS index
    _instance = None  # Class variable to hold the singleton instance
    

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SalesGPTAPI, cls).__new__(cls)
        return cls._instance

    def __init__(self, config_path: str, verbose: bool = False, max_num_turns: int = 10000):
        print("vwgwgagagagaegagae")
        if hasattr(self, '_initialized'):  # Check if the instance is already initialized
            return
        self._initialized = True  # Mark as initialized
        self.data_fields = ['Tipo_cliente', 'Tipo_documento', 'NIT', 'Nombre', 'Departamento', 'Dirección', 'Barrio', 'Celular', 'Correo', 'Placas', 'Tipo', 'Marca', 'Version', 'Modelo', 'Marca_producto', 'Referencia', 'Cantidad', 'Mayorista', 'Medio_pago']
        self.customer_info = {field: '' for field in self.data_fields}
        self.info_requested = False
        self.current_data_index = 0

        self.shift = 0

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
                index=current_data_index
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

            if self.info_requested and not self.shift:
                self.shift = 1
            elif self.info_requested and self.current_data_index < len(self.data_fields):
                self.customer_info[self.data_fields[self.current_data_index]] = sales_agent.conversation_history[-1]
                self.current_data_index+=1
                print("INFO", self.customer_info)
                print("INDEX", self.current_data_index)

                if all(value for value in self.customer_info.values()):
                    # Convert the dictionary to a string
                    self.customer_info["valor_venta"] = "300.000"
                    self.customer_info["producto"] = self.customer_info["Referencia"]
                    customer_info_str = "\n".join(f"{key}: {value}" for key, value in self.customer_info.items())

                    # Write the string to a text file
                    with open('customer_info.txt', 'w') as file:
                        file.write(customer_info_str)

                    # Optional: Print a message to confirm that the data is saved
                    print("Customer information saved to customer_info.txt")
                    

        sales_agent.step()


        print("JUEPUTA", sales_agent.conversation_history[-1])
        if len(sales_agent.conversation_history)>1:
            print(sales_agent.conversation_history[-2])
        if "<INFO_REQUESTED>" in sales_agent.conversation_history[-1]:
            print("ENTRAAAAAA", sales_agent.conversation_history[-1])
            self.info_requested = True

        if "<END_OF_CALL>" in sales_agent.conversation_history[-1]:
            print("Sales Agent determined it is time to end the conversation.")
            return "<END_OF_CALL>"

        reply = sales_agent.conversation_history[-1]

        if self.verbose:
            print("=" * 10)
            print(f"{sales_agent.salesperson_name}:{reply}")
        return {"name": sales_agent.salesperson_name, "reply": reply}
