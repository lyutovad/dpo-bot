# -*- coding: utf-8 -*-

import os
import random
import psycopg
import uuid
from langchain_community.llms import Ollama
from langchain_ollama.chat_models import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings
from langchain_postgres import PGVector
from langchain.text_splitter import RecursiveCharacterTextSplitter

from langchain.docstore.document import Document as LangChainDocument
from langchain_community.document_loaders import TextLoader
from langchain.retrievers import SelfQueryRetriever
from langchain.prompts import PromptTemplate

from langchain.chains.retrieval import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

from schemes import scheme_grading_exam, scheme_mba_ved, scheme_graduate, scheme_mba_business_strategy, scheme_two_diploma, scheme_resources, scheme_grading_test, scheme_grading_essay
from collections_list import collections_list

SEED = 42
random.seed(SEED)
os.environ['PYTHONHASHSEED'] = str(SEED)

POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")
POSTGRES_DB = os.getenv("POSTGRES_DB")

# OLLAMA_HOST= os.getenv("OLLAMA_HOST")
OLLAMA_HOST = "http://ollama2.cad.svc.cluster.local:11434"
# OLLAMA_MODEL=os.getenv("OLLAMA_MODEL")
OLLAMA_MODEL='llama3.1'

CONNECTION_STRING = f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
OPTIMAL_SIZE_CHANK = 1000
CHUNK_OVERLAP = 100

connect_string = f"host={POSTGRES_HOST} port ={POSTGRES_PORT} dbname={POSTGRES_DB} user={POSTGRES_USER} password={POSTGRES_PASSWORD}"
Connection = psycopg.connect(connect_string)

Query_Find_Collection = """
    SELECT f.name 
    FROM langchain_pg_collection f 
    JOIN langchain_pg_embedding s ON s.collection_id = f.uuid 
    WHERE EXISTS (
        SELECT 1 
        FROM unnest(%s::text[]) AS keyword 
        WHERE s.cmetadata::text ILIKE '%%' || keyword || '%%'
    );
    """

Query_Insert_Question_To_Db = """
    INSERT INTO not_answered (question, num_coll, global_error, id_rec, in_process, finished) VALUES (%s, %s, %s, %s, %s, %s);
    """

ollama_config = {
                "base_url": OLLAMA_HOST,
                "model": OLLAMA_MODEL,
                "temperature": 0.5,
                "num_ctx": 8192,
                "top_k": 12,
                # "num_predict": 2048,
                "repeat_penalty": 1.1,
                "top_p": 0.2
                }

                # ВАЖНО: Вы должны предоставить полную информацию по вопросам, связанным со стоимостью обучения и конкретных программах.
                # Если точного ответа на вопрос нет в предоставленном контексте, четко укажите на это и запросите конкретную информацию, необходимую для ответа.
                # Предоставляйте дополнительные пояснения и комментарии, когда это уместно.

                # Укажите конкретный раздел или программу в контексте, откуда вы взяли информацию для ответа.

prompt_template = """Вы консультант по образовательному процессу Всероссийской Академии Внешней Торговли (ВАВТ).

Внимательно прочитайте и проанализируйте предоставленный контекст перед ответом.
Отвечайте конкретно на поставленный вопрос, основываясь на предоставленном контексте. Пояснения и комментариии не выводите.
КРИТИЧНО: Если контекст непонятен, то запросите дополнительную информацию фразой "Для предоставления более конкретной информации, пожалуйста, уточните вопрос."
КРИТИЧНО: Если вы не нашли в предоставленном контексте нужной информации, не пытайтесь придумывать ответ, вместо этого говорите "Нет ответа на поставленный вопрос.".
ВАЖНО: Если в вопросе пользователя присутствует ненормативная лексика, то отвечайте фразой "Пожалуйста, не используйте такие слова в своих вопросах.".

Структурируйте ваш ответ, используя пункты или параграфы для улучшения читаемости.
Если в контексте есть противоречивая или неоднозначная информация, укажите на это в вашем ответе.


{context}

Вопрос пользователя: {input}

Ответ:"""


collection_name="course_documents"

class OllamaModel():

    def __init__(self):
        self.ollama = ChatOllama(**ollama_config)
        self.embeddings = OllamaEmbeddings(**ollama_config)
        self.ollama_gen = Ollama(**ollama_config)
        self.conn = Connection
        self.conn.autocommit = True


    def _pgvector_init_(self, collection_name: str, dir_name: str, files, directory = None):
        """
        Инициализация векторного хранилища
        Parameters:
        collection_name: название коллекции
        pre_delete_collection: удалять ли коллекцию для перезаписи
        """
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
            # self._load_documents_(directory)
            self._create_embeddings_collections_(directory, dir_name, files, collection_name)



    def _create_embeddings_collections_(self, directory, dir_name, files, collection_name, chunk_size=OPTIMAL_SIZE_CHANK, chunk_overlap=CHUNK_OVERLAP):

        print("Загружаем файлы...")
        for filename in os.listdir(directory):

            with open(f"{directory}/{filename}", 'r', encoding='utf-8') as file:
                document_text = file.read()

            keywords = None

            for f in files:
                if f['file_name']==filename:
                    keywords = f['keywords']

            # Join all text elements
            # document_text = '\n'.join(full_text)

            text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            # separators=["\n\n", "\n"],
            # separators=["\n\n", "\n", ": ", ". ", ", ", "; ", " "],
            separators=["\n\n", "\n", ".", " ", ""],
            )

            texts = text_splitter.split_text(document_text)

            self.documents = [LangChainDocument(page_content=t,
                                                metadata={
                                                    "context": collection_name,
                                                    "keywords": keywords,
                                                    "program_name": collection_name
                                                })  for t in texts]

            print(f"Создано {len(self.documents)} текстовых фрагментов из DOCX файла.")

            self.vectorstore.add_documents(self.documents)
            print(f"Загружено {len(self.documents)} текстовых фрагментов в векторную базу.")

    def load_documents(self, file_paths):
        documents = []
        for file_path in file_paths:
            loader = TextLoader(file_path, encoding='utf-8')
            documents.extend(loader.load())
        return documents

    def split_documents(self, documents):
        # docs = documents.split("\n\n")
        # for doc in docs:

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=10000,
            chunk_overlap=0,
            length_function=len,
            # separators=["\n\n", "\n", ".", " ", ";"]
            separators=["\n\n", "\n", ": ", ". ", ", ", "; ", " "],
        )
        return text_splitter.split_documents(documents)


    def create_vector_store(self, texts, collection):
        vector_store = PGVector.from_documents(
            texts,
            self.embeddings,
            connection=CONNECTION_STRING,
            collection_name=collection,
            use_jsonb=True,
            pre_delete_collection=True,
        )
        return vector_store

    def insert_question_to_db(self, question, num_coll, global_err):
        id_rec = uuid.uuid4()
        cursor = self.conn.cursor()
        
        try:
            cursor.execute(Query_Insert_Question_To_Db, (question, num_coll, global_err, id_rec, False, False))
        except Exception as e:
            print(f"Error: {e}")
        finally:
            cursor.close()

    def create_vectors(self, collection_name, file_paths, metadata_list):
        raw_documents = self.load_documents(file_paths)
        split_texts = self.split_documents(raw_documents)
        for i, doc in enumerate(split_texts):
            doc.metadata.update(metadata_list[i])
        self.vectorstore = self.create_vector_store(split_texts, collection_name)
        print(f'Создание векторов коллекции "{collection_name}" завершено')


    def ask_question(self, question, num_coll):
        print(f" Вопрос: {question}")

        if num_coll == 1:
            collection = 'МВА-Современные технологии управления ВЭД'
            attribute_info = scheme_mba_ved.attribute_info
            question = question + f'. Программа обучения: {collection}' 
            
        elif num_coll == 2:
            collection = 'Специалитет/магистратура + МВА'
            attribute_info = scheme_graduate.attribute_info
            question = question + f'. Программа обучения: {collection}' 

        elif num_coll == 3:
            collection = 'МВА-Стратегическое управление эффективностью бизнеса'
            attribute_info = scheme_mba_business_strategy.attribute_info
            question = question + f'. Программа обучения: {collection}' 

        elif num_coll == 4:
            collection = 'Программа двух дипломов (магистратура + МВА) Бизнес-администрирование'
            attribute_info = scheme_two_diploma.attribute_info
            question = question + f'. Программа обучения: {collection}' 

        elif num_coll == 5:
            collection = 'Критерии оценивания слушателя на экзамене по дисциплинам'
            attribute_info = scheme_grading_exam.attribute_info

        elif num_coll == 6:
            collection = 'Электронные библиотеки и ресурсы'
            attribute_info = scheme_resources.attribute_info

        elif num_coll == 7:
            collection = 'Критерии оценивания слушателя на зачете по дисциплинам'
            attribute_info = scheme_grading_test.attribute_info

        elif num_coll == 8:
            collection = 'Критерии оценивания эссе'
            attribute_info = scheme_grading_essay.attribute_info

        self.vectorstore = PGVector(
            connection=CONNECTION_STRING,
            embeddings=self.embeddings,
            collection_name=collection,
            use_jsonb=True,
            pre_delete_collection=False,
        )

        try:
# -------------------------------------------------------
            retriever = SelfQueryRetriever.from_llm(
            self.ollama,
            self.vectorstore,
            document_contents=pre_result,
            metadata_field_info=attribute_info,
            search_kwargs={"k": 3},
            verbose=True,
            fix_invalid=True
            )
            try:
                docs = retriever.invoke(question)
            except Exception as e:
                retriever = self.vectorstore.as_retriever(search_kwargs={"k": 2})
                docs = retriever.invoke(question)
                print('Ошибка!!!')
                print(e)
            if len(docs) == 0:
                retriever = self.vectorstore.as_retriever(search_kwargs={"k": 2})
                docs = retriever.invoke(question)
                print('as_retriever, 0')
            print(len(docs))
            input_data = {
                "input_documents": docs,
                "question": question,
            }

        # --------------------------------------------------------
            PROMPT = PromptTemplate(
                    template=prompt_template,
                    input_variables=["context", "input"]
                )
            question_answer_chain = create_stuff_documents_chain(self.ollama, PROMPT)
            chain = create_retrieval_chain(retriever, question_answer_chain)
            result = chain.invoke({"query": question, "input": input_data})
            print(result["answer"])

            if result["answer"] == "Нет ответа на поставленный вопрос.":
                self.insert_question_to_db(question, num_coll, False)

            return result["answer"]

        except Exception as e:
            self.insert_question_to_db(question, num_coll, True)
            print(e)
            return 'Нет ответа на поставленный вопрос.'
            

ollama_model = OllamaModel()

pre_result = """Эта коллекция содержит информацию о различных образовательных программах, включая программы MBA.
Документы охватывают такие темы, как требования к поступлению, содержание курсов, длительность обучения, стоимость, дату начала обучения,
требования к кандидатам (возраст, образование, опыт работы), информацию о выпускниках.
Каждый документ обычно содержит название программы, описание.
Некоторые документы могут включать статистику о трудоустройстве выпускников и отзывы студентов.
Дата начала обучения "start_date" в формате DD mmmm YYYY.
"""

questions = [
    # {
    #     'question': 'Какие есть электронные библиотеки?',
    #     'num_coll': 5
    # },

    # {
    #     'question': 'Напиши требования к оценке "отлично".',
    #     'num_coll': 5
    # },

    # {
    #     'question': 'Сколько нужно баллов, чтобы получить зачет?',
    #     'num_coll': 7
    # },

    # {
    #     'question': 'Какие существуют критерии оценивания эссе?',
    #     'num_coll': 8
    # },

    {
        'question': 'Кто такой Вася?',
        'num_coll': 5
    },

    {
        'question': 'Как поступить?',
        'num_coll': 4
    },

    # {
    #     'question': 'Какие нужны документы для поступления?',
    #     'num_coll': 1
    # },

    # {
    #     'question': 'Напиши содержание модуля 2.',
    #     'num_coll': 1
    # },
    # {
    #     'question': 'Напиши стоимость обучения.',
    #     'num_coll': 1
    # },
    #  {
    #     'question': 'Напиши карьерные перспективы для выпускников.',
    #     'num_coll': 1
    # },
    # {
    #     'question': 'Напиши стоимость обучения.',
    #     'num_coll': 2
    # },
    #  {
    #     'question': 'Перечисли дисциплины по программе.',
    #     'num_coll': 1
    # },

    # {
    #     'question': 'Перечисли дисциплины по программе.',
    #     'num_coll': 4
    # },

    # {
    #     'question': 'Напиши описание программы',
    #     'num_coll': 4
    # },

    # {
    #     'question': 'Какие есть дисциплины по специализации?',
    #     'num_coll': 3
    # },

    # {
    #     'question': 'Перечисли основные дисциплины по программе.',
    #     'num_coll': 3
    # },
    #  {
    #     'question': 'Когда начало обучения по программе?',
    #     'num_coll': 1
    # },
    # {
    #     'question': 'Какие нужны документы для поступления?',
    #     'num_coll': 2
    # },
    #  {
    #     'question': 'Какими навыками будет владеть выпускник?',
    #     'num_coll': 2
    # },
    # {
    #     'question': 'Какова длительность обучения?',
    #     'num_coll': 2
    # },
    # 'В каких компаниях работают выпускники программы MBA-Современные технологии управления ВЭД?',
    # 'Напиши структуру с наименованием дисциплины Современные тенденции развития и регулирования международной торговли',
    # 'Напиши трудоемкость курса Внешнеэкономическая деятельность России и Евразийского экономического союза',
    # 'Какая дисциплина в программе имеет трудоемкость (объем) 72 часа?',
    # 'Перечисли электронные библиотеки',
    # 'Как получить доступ к электронной библиотеке Scopus?',
    # 'Какие программы MBA есть в Академии?',
    # 'Напишите, пожалуйста, структуру и содержание дисциплины Внешнеэкономическая деятельность России и Евразийского экономического союза?',
    # 'Напиши цели и задачи дисциплины Современные тенденции развития и регулирования международной торговли',
    # 'Какие установлены возрастные ограничения при поступлении на программу?',
    # 'Мне больше шестидесяти лет. Смогу ли я поступить на программу MBA-Современные технологии управления ВЭД?',
    # 'Предоставь информацию о выпускниках Академии',
    # 'Какие модули входят в программу обучения МВА-Современные технологии управления ВЭД?',  
    # 'Кто разработчик курса Налогообложение внешнеторговых операций в РФ?',
    # 'Напиши планируемые результаты обучения по курсу Налогообложение внешнеторговых операций в РФ',
    # 'Напиши цели и задачи курса Управление изменениями в организациях ВЭД',
    # 'Напиши планируемые результаты обучения по курсу Особенности ведения бизнеса с отдельными зарубежными странами',
    # 'Кто разработчик курса Особенности ведения бизнеса с отдельными зарубежными странами?',
    # 'Напиши структуру и содержание курса Общий менеджмент – подходы и методы управления. Формы организационных структур.',
    # 'Кто разработчик курса Управление изменениями в организациях ВЭД?',
    # 'Напиши трудоемкость курса Налогообложение внешнеторговых операций в РФ',
]

# for q in questions:
#     print(f" Вопрос: {q['question']}")
#     ollama_model.ask_question2(q['question'], q['num_coll'])
#     print("\n")
