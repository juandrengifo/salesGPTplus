from copy import deepcopy
from typing import Any, Callable, Dict, List, Union

import json
import os

import logging

logging.basicConfig(level=logging.INFO)

import faiss
from langchain.embeddings.openai import OpenAIEmbeddings

from langchain.agents import AgentExecutor, LLMSingleActionAgent
from langchain.chains import LLMChain, RetrievalQA
from langchain.chains.base import Chain
from langchain.chat_models import ChatLiteLLM
from langchain.llms.base import create_base_retry_decorator
from litellm import acompletion
from pydantic import Field

from salesgpt.chains import SalesConversationChain, StageAnalyzerChain
from salesgpt.logger import time_logger
from salesgpt.parsers import SalesConvoOutputParser
from salesgpt.prompts import SALES_AGENT_TOOLS_PROMPT
from salesgpt.stages import CONVERSATION_STAGES
from salesgpt.templates import CustomPromptTemplateForTools
from salesgpt.tools import get_tools, setup_knowledge_base


def _create_retry_decorator(llm: Any) -> Callable[[Any], Any]:
    import openai

    errors = [
        openai.Timeout,
        openai.APIError,
        openai.APIConnectionError,
        openai.RateLimitError,
        openai.APIStatusError,
    ]
    return create_base_retry_decorator(error_types=errors, max_retries=llm.max_retries)


class SalesGPT(Chain):
    """Controller model for the Sales Agent."""
    conversation_history: List[str] = []
    conversation_stage_id: str = "1"
    current_conversation_stage: str = CONVERSATION_STAGES.get("1")
    stage_analyzer_chain: StageAnalyzerChain = Field(...)
    sales_agent_executor: Union[AgentExecutor, None] = Field(...)
    knowledge_base: Union[RetrievalQA, None] = Field(...)
    sales_conversation_utterance_chain: SalesConversationChain = Field(...)
    conversation_stage_dict: Dict = CONVERSATION_STAGES
    # Additional attributes
    data_fields = ['Tipo_cliente', 'Tipo_documento', 'NIT', 'Nombre', 'Departamento', 'Dirección', 'Barrio', 'Celular', 'Correo', 'Placas', 'Tipo', 'Marca', 'Version', 'Modelo', 'Producto', 'Marca_producto', 'Referencia', 'Cantidad', 'Mayorista', 'Valor', 'Medio_pago']
    customer_info = {field: '' for field in data_fields}
    info_requested = False
    current_data_index = 0


    model_name: str = "gpt-4-1106-preview"

    use_tools: bool = False
    salesperson_name: str = "VictorIA"
    salesperson_role: str = "Agente representante de ventas"
    company_name: str = "Baterias Mac"
    company_business: str = """Baterías MAC es una marca de Clarios, el mayor fabricante de baterías para automóviles del mundo. Actualmente, el fabricante líder a nivel global suministra aproximadamente 150 millones de baterías cada año a fabricantes de automóviles y distribuidores del mercado de recambio. Su completa gama de baterías, con tecnología de plomo – ácido y de iones de litio, proporciona energía a casi todos los tipos de vehículos, desde los convencionales hasta los vehículos con sistemas Start Stop Avanzado.

El sistema de reciclaje manejado por este fabricante ha contribuido a que las baterías de automóviles sean el bien de consumo que más se recicla en el mundo. A nivel mundial, 16,000 empleados desarrollan, fabrican, distribuyen y reciclan baterías en más de 56 ubicaciones sirviendo a más de 150 países, y cuenta con más de 130 años de innovación y crecimiento."""
    company_values: str = """NUESTRA MISIÓN ES CREAR LAS MEJORES BATERÍAS DEL MUNDO, ESENCIALES PARA EL FUTURO EN EVOLUCIÓN DEL TRANSPORTE.
Desarrollamos ideas perspicaces y las convertimos en realidades impactantes. Nos anticipamos a las necesidades de los clientes y los mercados a los que prestamos servicios y ofrecemos soluciones con agilidad y flexibilidad."""
    conversation_purpose: str = "Vender baterías de carro"
    conversation_type: str = "call"

    def retrieve_conversation_stage(self, key):
        return self.conversation_stage_dict.get(key, "1")

    @property
    def input_keys(self) -> List[str]:
        return []

    @property
    def output_keys(self) -> List[str]:
        return []

    @time_logger
    def seed_agent(self):
        # Step 1: seed the conversation
        self.current_conversation_stage = self.retrieve_conversation_stage("1")
        self.conversation_history = []

    @time_logger
    def determine_conversation_stage(self):
        self.conversation_stage_id = self.stage_analyzer_chain.run(
            conversation_history="\n".join(self.conversation_history).rstrip("\n"),
            conversation_stage_id=self.conversation_stage_id,
            conversation_stages="\n".join(
                [
                    str(key) + ": " + str(value)
                    for key, value in CONVERSATION_STAGES.items()
                ]
            ),
        )

        print(f"Conversation Stage ID: {self.conversation_stage_id}")
        self.current_conversation_stage = self.retrieve_conversation_stage(
            self.conversation_stage_id
        )

        print(f"Conversation Stage: {self.current_conversation_stage}")



    def write_data_to_file(self):
        filename = "customer_info.txt"
        with open(filename, 'a') as file:  # Append mode
            for key, value in self.customer_info.items():
                file.write(f"{key}: {value}\n")
            file.write("\n")  # Add a newline to separate entries

    # Override the human_step method
    def human_step(self, human_input):
        # Process human input
        human_input = "User: " + human_input + " <END_OF_TURN>"
        self.conversation_history.append(human_input)

        if self.info_requested:
            self._extract_and_store_data(human_input)
            if all(self.customer_info.values()):
                self.write_data_to_file()
                self.info_requested = False




    

    @time_logger
    def step(self, stream: bool = False):
        """
        Args:
            stream (bool): whether or not return
            streaming generator object to manipulate streaming chunks in downstream applications.
        """
        if not stream:
            self._call(inputs={})
        else:
            return self._streaming_generator()

    @time_logger
    def astep(self, stream: bool = False):
        """
        Args:
            stream (bool): whether or not return
            streaming generator object to manipulate streaming chunks in downstream applications.
        """
        if not stream:
            self._acall(inputs={})
        else:
            return self._astreaming_generator()

    @time_logger
    def acall(self, *args, **kwargs):
        raise NotImplementedError("This method has not been implemented yet.")

    @time_logger
    def _prep_messages(self):
        """
        Helper function to prepare messages to be passed to a streaming generator.
        """
        prompt = self.sales_conversation_utterance_chain.prep_prompts(
            [
                dict(
                    conversation_stage=self.current_conversation_stage,
                    conversation_history="\n".join(self.conversation_history),
                    salesperson_name=self.salesperson_name,
                    salesperson_role=self.salesperson_role,
                    company_name=self.company_name,
                    company_business=self.company_business,
                    company_values=self.company_values,
                    conversation_purpose=self.conversation_purpose,
                    conversation_type=self.conversation_type,
                )
            ]
        )

        inception_messages = prompt[0][0].to_messages()

        message_dict = {"role": "system", "content": inception_messages[0].content}

        if self.sales_conversation_utterance_chain.verbose:
            print("\033[92m" + inception_messages[0].content + "\033[0m")
        return [message_dict]

    @time_logger
    def _streaming_generator(self):
        """
        Sometimes, the sales agent wants to take an action before the full LLM output is available.
        For instance, if we want to do text to speech on the partial LLM output.

        This function returns a streaming generator which can manipulate partial output from an LLM
        in-flight of the generation.

        Example:

        >> streaming_generator = self._streaming_generator()
        # Now I can loop through the output in chunks:
        >> for chunk in streaming_generator:
        Out: Chunk 1, Chunk 2, ... etc.
        See: https://github.com/openai/openai-cookbook/blob/main/examples/How_to_stream_completions.ipynb
        """

        messages = self._prep_messages()

        return self.sales_conversation_utterance_chain.llm.completion_with_retry(
            messages=messages,
            stop="<END_OF_TURN>",
            stream=True,
            model=self.model_name,
        )

    async def acompletion_with_retry(self, llm: Any, **kwargs: Any) -> Any:
        """Use tenacity to retry the async completion call."""
        retry_decorator = _create_retry_decorator(llm)

        @retry_decorator
        async def _completion_with_retry(**kwargs: Any) -> Any:
            # Use OpenAI's async api https://github.com/openai/openai-python#async-api
            return await acompletion(**kwargs)

        return await _completion_with_retry(**kwargs)

    async def _astreaming_generator(self):
        """
        Asynchronous generator to reduce I/O blocking when dealing with multiple
        clients simultaneously.

        Sometimes, the sales agent wants to take an action before the full LLM output is available.
        For instance, if we want to do text to speech on the partial LLM output.

        This function returns a streaming generator which can manipulate partial output from an LLM
        in-flight of the generation.

        Example:

        >> streaming_generator = self._astreaming_generator()
        # Now I can loop through the output in chunks:
        >> async for chunk in streaming_generator:
            await chunk ...
        Out: Chunk 1, Chunk 2, ... etc.
        See: https://github.com/openai/openai-cookbook/blob/main/examples/How_to_stream_completions.ipynb
        """

        messages = self._prep_messages()

        return await self.acompletion_with_retry(
            llm=self.sales_conversation_utterance_chain.llm,
            messages=messages,
            stop="<END_OF_TURN>",
            stream=True,
            model=self.model_name,
        )

    def _extract_and_store_data(self, message: str) -> None:
        """Extracts and stores data from the message."""
        if "<INFO_REQUESTED>" in message and 0 <= self.current_data_index < len(self.data_fields):
            current_field = self.data_fields[self.current_data_index]
            extracted_data = self._parse_data_from_message(message)
            logging.info(f"Extracted Data: {extracted_data}, Current Index: {self.current_data_index}")
            if extracted_data:  # Check if valid data is extracted
                self.customer_info[current_field] = extracted_data
                self.current_data_index += 1  # Increment only if valid data is extracted
                logging.info(f"Data Index Incremented to: {self.current_data_index}")

    def _parse_data_from_message(self, message: str) -> str:
        """Parses specific data from the message based on the field."""
        # Implement logic to parse specific data from the message
        # This example extracts everything after the salesperson's name
        data_start = message.find(":") + 1
        data = message[data_start:].split("<INFO_REQUESTED>")[0].strip()
        return data if data else None

    def _handle_apology_message(self):
        """Handles the scenario when AI issues an apology message."""
        # Implement your logic for handling apology messages
        # Example: Send a message to try again or maintain the current index
        self.conversation_history.append(self.salesperson_name + ": Could you please provide the information again?")
        # Do not reset the index here

    def _call(self, inputs: Dict[str, Any]) -> None:
        """Run one step of the sales agent."""
        print("INFO_REQUESTED status:", self.info_requested)

        # Generate agent's utterance
        ai_message = self._generate_ai_message()

        # Add agent's response to conversation history
        self.conversation_history.append(ai_message)

        # Extract and store data if information is requested
        if "<INFO_REQUESTED>" in ai_message:
            self.info_requested = True
            self._extract_and_store_data(ai_message)
        else:
            self.info_requested = False

        # Reset the index if all fields are filled
        if all(value for value in self.customer_info.values()):
            print("HERE?")
            self._finalize_data_collection()

        # Check for special cases like apology messages
        if "I apologize" in ai_message:
            self._handle_apology_message()

        # Print AI message and customer info for debugging
        self._log_debug_information()

    def _finalize_data_collection(self):
        """Finalizes data collection and performs necessary actions."""
        self._write_data_to_file()
        self._reset_data_collection()

    def _reset_data_collection(self):
        """Resets data collection for the next conversation."""
        logging.info("Resetting data collection")
        self.current_data_index = 0
        self.customer_info = {field: '' for field in self.data_fields}
        self.info_requested = False



    def _log_debug_information(self):
            return 0
            print("AI Message:", self.conversation_history[-1])
            print(f"INFO_REQUESTED status: {self.info_requested}")
            print(f"Current field index: {self.current_data_index}")
            print(f"Current customer info: {self.customer_info}")

    def _generate_ai_message(self):
        """Generates the AI's response based on the current conversation context."""
        if self.use_tools:
            ai_message = self.sales_agent_executor.run(
                input="",
                conversation_stage=self.current_conversation_stage,
                conversation_history="\n".join(self.conversation_history),
                salesperson_name=self.salesperson_name,
                salesperson_role=self.salesperson_role,
                company_name=self.company_name,
                company_business=self.company_business,
                company_values=self.company_values,
                conversation_purpose=self.conversation_purpose,
                conversation_type=self.conversation_type,
            )
        else:
            ai_message = self.sales_conversation_utterance_chain.run(
                conversation_stage=self.current_conversation_stage,
                conversation_history="\n".join(self.conversation_history),
                salesperson_name=self.salesperson_name,
                salesperson_role=self.salesperson_role,
                company_name=self.company_name,
                company_business=self.company_business,
                company_values=self.company_values,
                conversation_purpose=self.conversation_purpose,
                conversation_type=self.conversation_type,
            )
        
        # Format AI message and append <END_OF_TURN> if needed
        agent_name = self.salesperson_name
        ai_message = agent_name + ": " + ai_message
        if "<END_OF_TURN>" not in ai_message:
            ai_message += " <END_OF_TURN>"
        
        return ai_message


    def _handle_apology_message(self):
        """Handles the scenario when AI issues an apology message."""
        # Example: Repeat the last question or provide a default response
        # This is a placeholder; adapt as per your conversation flow
        last_question = self._get_last_question()
        if last_question:
            self.conversation_history.append(self.salesperson_name + ": " + last_question)

    def _get_last_question(self) -> str:
        """Retrieves the last question asked before the apology message."""
        # Implement logic to retrieve the last question from conversation history
        # This is a placeholder implementation
        for message in reversed(self.conversation_history):
            if "?" in message:
                return message.split(":")[-1].strip()
        return ""

    @classmethod
    @time_logger
    def from_llm(cls, llm: ChatLiteLLM, verbose: bool = False, **kwargs) -> "SalesGPT":
        stage_analyzer_chain = StageAnalyzerChain.from_llm(llm, verbose=verbose)
        
        # Use custom prompt logic if specified
        if "use_custom_prompt" in kwargs and kwargs["use_custom_prompt"] == "True":
            use_custom_prompt = deepcopy(kwargs["use_custom_prompt"])
            custom_prompt = deepcopy(kwargs["custom_prompt"])
            del kwargs["use_custom_prompt"]
            del kwargs["custom_prompt"]
            sales_conversation_utterance_chain = SalesConversationChain.from_llm(
                llm, verbose=verbose, use_custom_prompt=use_custom_prompt, custom_prompt=custom_prompt
            )
        else:
            sales_conversation_utterance_chain = SalesConversationChain.from_llm(llm, verbose=verbose)
        
        # Initialize tools if specified
        if "use_tools" in kwargs and (kwargs["use_tools"] == "True" or kwargs["use_tools"]):
            path_to_faiss_index = kwargs.get("product_catalog", "salesgpt/embeddings.index")
            faiss_index, embeddings_model = setup_knowledge_base(path_to_faiss_index)
            tools = get_tools(faiss_index, embeddings_model)

            prompt = CustomPromptTemplateForTools(
                template=SALES_AGENT_TOOLS_PROMPT,
                tools_getter=lambda x: tools,
                input_variables=[
                    "input", "intermediate_steps", "salesperson_name", "salesperson_role",
                    "company_name", "company_business", "company_values", "conversation_purpose",
                    "conversation_type", "conversation_history",
                ],
            )
            llm_chain = LLMChain(llm=llm, prompt=prompt, verbose=verbose)
            tool_names = [tool.name for tool in tools]
            output_parser = SalesConvoOutputParser(ai_prefix=kwargs["salesperson_name"])
            sales_agent_with_tools = LLMSingleActionAgent(
                llm_chain=llm_chain,
                output_parser=output_parser,
                stop=["\nObservation:"],
                allowed_tools=tool_names,
            )
            sales_agent_executor = AgentExecutor.from_agent_and_tools(
                agent=sales_agent_with_tools, tools=tools, verbose=verbose
            )
        else:
            sales_agent_executor = None

        # Removed the knowledge_base attribute
        return cls(
            stage_analyzer_chain=stage_analyzer_chain,
            sales_conversation_utterance_chain=sales_conversation_utterance_chain,
            sales_agent_executor=sales_agent_executor,
            model_name=llm.model,
            verbose=verbose,
            **kwargs
        )