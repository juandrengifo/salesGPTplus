import os
from salesgpt.agents import SalesGPT
from langchain.chat_models import ChatLiteLLM
from dotenv import load_dotenv

load_dotenv()  # make sure you have .env file with your API keys, eg., OPENAI_API_KEY=sk-xxx

# select your model - we support 50+ LLMs via LiteLLM https://docs.litellm.ai/docs/providers
llm = ChatLiteLLM(temperature=0.4, model_name="gpt-4-1106-preview")

sales_agent = SalesGPT.from_llm(llm, use_tools=True, verbose=False,
                                product_catalog="examples/catalog.txt",
                                salesperson_name="Ted Lasso",
                                salesperson_role="Agente representante de ventas",
                                company_name="Baterias Mac",
                                company_business='''Baterías MAC es una marca de Clarios, el mayor fabricante de baterías para automóviles del mundo. Actualmente, el fabricante líder a nivel global suministra aproximadamente 150 millones de baterías cada año a fabricantes de automóviles y distribuidores del mercado de recambio. Su completa gama de baterías, con tecnología de plomo – ácido y de iones de litio, proporciona energía a casi todos los tipos de vehículos, desde los convencionales hasta los vehículos con sistemas Start Stop Avanzado.

El sistema de reciclaje manejado por este fabricante ha contribuido a que las baterías de automóviles sean el bien de consumo que más se recicla en el mundo. A nivel mundial, 16,000 empleados desarrollan, fabrican, distribuyen y reciclan baterías en más de 56 ubicaciones sirviendo a más de 150 países, y cuenta con más de 130 años de innovación y crecimiento.'''
                                )

sales_agent.seed_agent()
sales_agent.determine_conversation_stage()  # optional for demonstration, built into the prompt

# Start conversation loop
while True:
    # Agent step
    sales_agent.step()

    # User input
    user_input = input('Your response: ')
    if user_input.lower() == 'exit':
        print("Exiting conversation.")
        break
    sales_agent.human_step(user_input)

    # Determine next conversation stage
    sales_agent.determine_conversation_stage()

# End of conversation
