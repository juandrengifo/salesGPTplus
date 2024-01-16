import pandas as pd
import numpy as np
import faiss
import openai
from openai import OpenAI

client = OpenAI()

# Load data from Excel file (assuming the file has a .xlsx extension)
excel_file_path = '../examples/catalogo.xlsx'  # Replace with your actual file path
df = pd.read_excel(excel_file_path)

# Combine 'MARCA' and 'MODELO / VEHÍCULO' columns into a single text field
print(df.columns)
df['combined_text'] = df['MARCA'] + " " + df['MODELO / VEHICULO']

def get_embedding(text, model="text-embedding-ada-002"):
    # Ensure the text is a string
    text = str(text).replace("\n", " ")
    response = client.embeddings.create(input=[text], model=model)
    return np.array(response.data[0].embedding)


# Generate embeddings for the combined text
embeddings = np.array([get_embedding(text) for text in df['combined_text']])

# Create FAISS index
dimension = embeddings.shape[1]
index = faiss.IndexFlatL2(dimension)
index.add(embeddings)

# Save the index
faiss.write_index(index, 'embeddingsV2.index')
