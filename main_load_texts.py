from langchain_main import OllamaModel 
from schemes import scheme_grading_exam, scheme_mba_ved, scheme_graduate, scheme_mba_business_strategy, scheme_two_diploma, scheme_resources
import json
from collections_list import collections_list



def create_embeddings():
    ollama_model = OllamaModel()

    for coll in collections_list:
        ollama_model.create_vectors(coll['name'], coll['file_paths'], coll['metadata_list'])

if __name__ == "__main__":

    create_embeddings()