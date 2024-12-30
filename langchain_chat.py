# -*- coding: utf-8 -*-

import os
import json
from langchain_community.llms import Ollama
from langchain_ollama.chat_models import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings
from langchain_postgres import PGVector
from langchain.text_splitter import RecursiveCharacterTextSplitter

from langchain.docstore.document import Document as LangChainDocument
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain.prompts import PromptTemplate
from langchain.chains.query_constructor.base import AttributeInfo


from langchain.chains.retrieval import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

from langchain.memory import ConversationBufferMemory
from langchain.chains.conversation.base import ConversationChain
from langchain_community.query_constructors.pgvector import PGVectorTranslator

from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain.schema.messages import HumanMessage, AIMessage
# from langchain.memory import ChatMessageHistory
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables import RunnablePassthrough
from typing import Dict, Any, List

OLLAMA_HOST= os.getenv("OLLAMA_HOST")
OLLAMA_MODEL=os.getenv("OLLAMA_MODEL")
CONNECTION_STRING = "postgresql+psycopg://postgres:123@192.168.0.170:5432/dpo_bot"
OPTIMAL_SIZE_CHANK = 2000
CHUNK_OVERLAP = 200

ollama_config = {
                "base_url": OLLAMA_HOST,
                "model": OLLAMA_MODEL,
                "temperature": 0.2,
                "num_ctx": 8192,
                "top_k": 10,
                # "num_predict": 2048,
                "repeat_penalty": 1.1,
                "top_p": 0.2
                }

prompt_template = """Вы консультант по образовательному процессу Всероссийской Академии Внешней Торговли (ВАВТ).
                    Пожалуйста, дайте подробный ответ на вопрос, основываясь на предоставленном контексте.
                    Отвечайте конкретно на поставленный вопрос. 
                    Внимательно прочитайте и проанализируйте предоставленный контекст перед ответом. 
                    КРИТИЧНО: Если контекст непонятен, то запросите дополнительную информацию фразой "Пожалуйста, уточните вопрос."
                    Если вопрос касается предыдущих вопросов или ответов, обратитесь к истории диалога.
                    ВАЖНО: Вы должны предоставить полную информацию по вопросам, связанным со стоимостью обучения и конкретных программах.
                    Укажите конкретный раздел или программу в контексте, откуда вы взяли информацию для ответа.
                    Структурируйте ваш ответ, используя пункты или параграфы для улучшения читаемости. 
                    Если в контексте есть противоречивая или неоднозначная информация, укажите на это в вашем ответе. 
                    Если точного ответа на вопрос нет в предоставленном контексте, четко укажите на это и запросите конкретную информацию, необходимую для ответа.  
                    КРИТИЧНО: Если вы не нашли в предоставленном контексте нужной информации, не пытайтесь придумывать ответ, вместо этого говорите "В предоставленных документах нет ответа на поставленный вопрос.". 
                    Предоставляйте дополнительные пояснения и комментарии, когда это уместно.
                    Отвечайте только на русском языке.
                    

                    {context}

                    История диалога:
                    {chat_history}

                    Вопрос пользователя: {input}

                    Ответ:"""

attribute_info = [
    AttributeInfo(
        name="context",
        description="Название учебной дисциплины или программы",
        type="string",
    ),
    AttributeInfo(
        name="key_words",
        description="Список ключевых слов и словосочетаний",
        type="list[string]",
    ),
     AttributeInfo(
        name="program_name",
        description="Название учебной программы",
        type="string",
    ),
]

class OllamaModel():

    def __init__(self):
        self.ollama = ChatOllama(**ollama_config)
        self.embeddings = OllamaEmbeddings(**ollama_config)
        self.ollama_gen = Ollama(**ollama_config)
        self.memory = ConversationBufferMemory(input_key="input", memory_key="history")
        self.vectorstore = None
        self.chain = None
        self.retriever = None

    def _pgvector_init_(self, collection_name: str, dir_name: str, files, directory = None):
        if directory:
            pre_delete_collection = True
        else:
            pre_delete_collection = False
        self.vectorstore = PGVector(
            connection=CONNECTION_STRING,
            embeddings=self.embeddings,
            collection_name=collection_name,
            use_jsonb=True,
            pre_delete_collection=False,
        )
    
        if pre_delete_collection:
            print("Построение Embeddings...")
            self._create_embeddings_collections_(directory, dir_name, files, collection_name)

    
    def _create_embeddings_collections_(self, directory, dir_name, files, collection_name, chunk_size=OPTIMAL_SIZE_CHANK, chunk_overlap=CHUNK_OVERLAP):

        print("Загружаем файлы...")
        for filename in os.listdir(directory):

            with open(f"{directory}/{filename}", 'r', encoding='utf-8') as file:
                document_text = file.read()
            
            key_words = None

            for f in files:
                if f['file_name']==filename:
                    key_words = f['key_words']

            text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ": ", ". ", ", ", "; ", " "],
                                )

            texts = text_splitter.split_text(document_text)

            self.documents = [LangChainDocument(page_content=t, 
                                                metadata={
                                                    "context": dir_name,
                                                    "key_words": key_words,
                                                    "program_name": collection_name
                                                })  for t in texts]

            print(f"Создано {len(self.documents)} текстовых фрагментов из DOCX файла.")
            
            self.vectorstore.add_documents(self.documents)
            print(f"Загружено {len(self.documents)} текстовых фрагментов в векторную базу.")
    
    def format_context(self, documents: List[LangChainDocument]) -> str:
        return "\n\n".join([doc.page_content for doc in documents])
    
    def format_chat_history(self, chat_history: List[HumanMessage | AIMessage]) -> str:
        formatted_history = []
        for message in chat_history[-5:]:  # Ограничиваем историю последними 5 сообщениями
            if isinstance(message, HumanMessage):
                formatted_history.append(f"Человек: {message.content}")
            elif isinstance(message, AIMessage):
                formatted_history.append(f"ИИ: {message.content}")
        return "\n".join(formatted_history)

    def setup_chain(self, collection_name, question):
        try:

            self.vectorstore = PGVector(
                    connection=CONNECTION_STRING,
                    embeddings=self.embeddings,
                    collection_name=collection_name,
                    use_jsonb=True,
                    pre_delete_collection=False,
                )
          
            pre_result = f"Информация по программе \"{collection_name}\", дисциплинах в нее входящих, их целях, задачах, результатах, трудоемкости и структуре."

            self.retriever = SelfQueryRetriever.from_llm(
                self.ollama,
                self.vectorstore,
                document_contents=pre_result,
                metadata_field_info=attribute_info,
                enable_limit=True,
                valid_operators=["eq", "in", "lt", "lte", "gt", "gte", "ne", "or", "and"],
                search_kwargs={"k": 2},
                verbose=True,
                # structured_query_translator=PGVectorTranslator(),
                # structured_query_translator=self.custom_translator
                )


            PROMPT = PromptTemplate(
                    template=prompt_template, input_variables=["context", "chat_history", "input"]
                )
            
            self.chain = (
                {
                    "context": RunnablePassthrough(), 
                    "input": RunnablePassthrough(),
                    "chat_history": RunnablePassthrough()
                }
                | PROMPT
                | self.ollama
            )

        except Exception as e:
            print(e)
    

    def ask_question(self, collection_name: str, question: str, chat_history: InMemoryChatMessageHistory) -> str:
        if not self.chain:
            self.setup_chain(collection_name, question)

        retrieved_docs = self.retriever.invoke(question)
        formatted_context = self.format_context(retrieved_docs)

        runnable_with_message_history = RunnableWithMessageHistory(
            self.chain,
            lambda session_id: chat_history,
            input_messages_key="input",
            history_messages_key="chat_history"
        )

        formatted_history = self.format_chat_history(chat_history.messages)

        result = runnable_with_message_history.invoke(
            {
                "input": question,
                "context": formatted_context,  
                "chat_history": formatted_history
             },

            {"configurable": {"session_id": "default"}}
        )

        return result
  
ollama_model = OllamaModel()
chat_history = InMemoryChatMessageHistory()

questions = [
    # 'Напиши цель и задачи дисциплины Современные тенденции развития и регулирования международной торговли.',
    # 'Напиши объем дисциплины Внешнеэкономическая деятельность России и Евразийского экономического союза в часах',
    # 'Когда начало обучения по программе МВА - Современные технологии управления ВЭД?',
    # 
    # 'Напиши стоимость обучения по программе МВА - Современные технологии управления ВЭД.',
    # 
    # 'В каких компаниях работают выпускники программы MBA?',
    'Какие нужны документы для поступления на программу МВА - Современные технологии управления ВЭД?',
    # 'Какие программы MBA есть в Академии?',
    # 'Напиши предыдущий вопрос',
    'Напиши вид итоговой аттестации по дисциплине "Современные тенденции развития и регулирования международной торговли".',
    'Напиши цель и задачи этой дисциплины.',
    'Напиши результаты обучения по этой дисциплины.',
    # 'Напиши предыдущий вопрос',
]

for question in questions:
    try:
        answer = ollama_model.ask_question('МВА - Современные технологии управления ВЭД', question, chat_history)
        print(f"Вопрос: {question}")
        print(f"Ответ: {answer}")
        print("-" * 50)
        chat_history.add_user_message(question)
        chat_history.add_ai_message(answer)
    except Exception as e:
            print(e)