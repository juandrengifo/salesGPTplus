import faiss
from langchain.agents import Tool
from langchain.embeddings.openai import OpenAIEmbeddings
from openai import OpenAI
import numpy as np
import pandas as pd

# Load the vehicle data from CSV file
vehicle_data_path = 'examples/catalogo.csv'  # Replace with your actual file path
vehicle_data = pd.read_csv(vehicle_data_path)

def load_faiss_index(path_to_faiss_index):
    """
    Load the pre-computed FAISS index from a file.
    """
    return faiss.read_index(path_to_faiss_index)

client = OpenAI()

# Function to get embeddings from OpenAI
def get_embedding(text, model="text-embedding-ada-002"):
    text = text.replace("\n", " ")
    return client.embeddings.create(input = [text], model=model).data[0].embedding

def search_battery_options(query, faiss_index, model="text-embedding-ada-002"):
    """
    Search for battery options based on the query.
    """
    # Generate embedding for the query
    query_embedding = get_embedding(query)
    query_embedding = np.array(query_embedding).reshape(1, -1).astype('float32')

    # Search the FAISS index
    D, I = faiss_index.search(query_embedding, k=1)
    index = I[0][0]

    # Use the loaded vehicle_data DataFrame
    battery_options = get_battery_option_from_index(index, vehicle_data)
    return f"Battery options for your query: {battery_options}"


def setup_knowledge_base(path_to_faiss_index):
    """
    Set up the knowledge base with the FAISS index.
    """
    # Load the pre-computed FAISS index
    faiss_index = load_faiss_index(path_to_faiss_index)

    return faiss_index, "text-embedding-ada-002" # Returns the model identifier instead of embedding model object


def get_tools(faiss_index, embeddings_model):
    battery_search_tool = Tool(
        name="VehicleBatterySearch",
        func=lambda query: search_battery_options(query, faiss_index, embeddings_model),
        description="Search for battery options based on car model and year"
    )
    return [battery_search_tool]

def get_battery_option_from_index(index, vehicle_data):
    """
    Map the index from the FAISS search to the actual battery options along with brand names.

    :param index: The index returned by the FAISS search.
    :param vehicle_data: DataFrame containing vehicle and battery information.
    :return: String containing the battery options with brand names for the given index.
    """
    if 0 <= index < len(vehicle_data):
        battery_options_with_brands = []
        # Identifying columns that include brand names and options
        battery_option_columns = [col for col in vehicle_data.columns if "Opción" in col or "Op" in col]

        for col in battery_option_columns:
            option = vehicle_data.iloc[index][col]
            if pd.notna(option):
                brand_name = col.split()[0]  # Extracting brand name (assuming it's the first word in the column name)
                battery_options_with_brands.append(f"{brand_name} - {option}")

        return ', '.join(battery_options_with_brands) if battery_options_with_brands else "No battery options found"
    else:
        return "No battery options found for the given query."

