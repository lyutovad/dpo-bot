import os
import pandas as pd
from langsmith import Client
from langsmith.schemas import Example, Run
from langsmith.evaluation import evaluate
from langchain import hub
from langchain.chat_models import ChatOllama

from langchain_main import DPOBOT

LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2")
LANGCHAIN_ENDPOINT = os.getenv("LANGCHAIN_ENDPOINT")
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT")

OLLAMA_HOST= os.getenv("OLLAMA_HOST")
OLLAMA_MODEL=os.getenv("OLLAMA_MODEL")

# собираем тестовый датасет
# client = Client()

# df = pd.read_excel('files/testing_rag.xlsx')

# examples = []
# for i, row in df.iterrows():
#     examples.append((row["question"], row["answer"]))


# dataset_name = "DPO RAG QA"
# dataset = client.create_dataset(dataset_name=dataset_name)
# inputs, outputs = zip(
#     *[({"question": text}, {"ground_truth": label}) for text, label in examples]
# )
# client.create_examples(inputs=inputs, outputs=outputs, dataset_id=dataset.id)

# проверяем работу RAG
dpo = DPOBOT()
num_coll=3

dataset_name = "DPO RAG QA"

def correct_answer(root_run: Run, example: Example) -> dict:
    score = root_run.outputs.get("output") == example.outputs.get("answer")
    return {"score": int(score), "key": "correct_answer"}


results = evaluate(
    lambda inputs: dpo.ask_question(inputs["question"], num_coll=num_coll),
    data=dataset_name,
    evaluators=[correct_answer],
    experiment_prefix="DPO RAG Queries",
    description="Testing the baseline system.", 
)

def predict_rag_answer(example: dict):
    """Use this for answer evaluation"""
    response = dpo.ask_question(example["question"], num_coll=num_coll)
    return {"answer": response}

grade_prompt_answer_accuracy = prompt = hub.pull("langchain-ai/rag-answer-vs-reference")

def answer_evaluator(run, example) -> dict:
    """
    A simple evaluator for RAG answer accuracy
    """
    # Get question, ground truth answer, RAG chain answer
    input_question = example.inputs["question"]
    reference = example.outputs["ground_truth"]
    prediction = run.outputs["answer"]
    
    llm = ChatOllama(
        base_url=OLLAMA_HOST,  # Пример: ваш Ollama-сервер
        model=OLLAMA_MODEL,
        temperature=0,
        )

    answer_grader = grade_prompt_answer_accuracy | llm

    # Run evaluator
    score = answer_grader.invoke({"question": input_question,
                                  "correct_answer": reference,
                                  "student_answer": prediction})                                  
    score = score["Score"]

    return {"key": "answer_v_reference_score", "score": score}

print(grade_prompt_answer_accuracy)

experiment_results = evaluate(
    predict_rag_answer,
    data=dataset_name,
    evaluators=[answer_evaluator],
    experiment_prefix="rag-answer-v-reference",
)


# test_example = {"question": "Тестовый вопрос"}
# res = predict_rag_answer(test_example)
# print(res)