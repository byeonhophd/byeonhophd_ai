from llama_index.core import (
    SimpleDirectoryReader,
    VectorStoreIndex,
    StorageContext
)

from llama_index.vector_stores.faiss import FaissVectorStore
from llama_index.core.storage.index_store.simple_index_store import SimpleIndexStore
from llama_index.core.storage.docstore.simple_docstore import SimpleDocumentStore
from utils import RBLNBGEM3Embeddings

from absl import app, flags, logging
import faiss
import os
import json

FLAGS = flags.FLAGS

os.environ["LLAMA_INDEX_CACHE_DIR"]="./tmp" # Designate LlamaIndex Cache directory


flags.DEFINE_string("vector_store_dir", "law_data", "Directory to the vector store")
flags.DEFINE_string("compiled_embedding_model", "bge-m3", "Directory to compiled HuggingFace embedding model")
flags.DEFINE_bool("debug", True, "Enable debug level logging")
flags.DEFINE_bool("load_from_storage", False, "Load storage context from the storage")
flags.DEFINE_integer("chunk_size", 1024, "Text chunk size")
flags.DEFINE_integer("chunk_overlap_size", 100, "Text chunk overlap size")


from llama_index.core.schema import Document



def load_json_files(folder_path):
    """
    Load and process JSON files in the given folder.
    Assumes each JSON contains a list of {"title": ..., "content": ...}.
    """
    documents = []
    for filename in os.listdir(folder_path):
        if filename.endswith(".json"):
            file_path = os.path.join(folder_path, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        if "content" in item and "title" in item:
                            doc = Document(
                                text=item["content"],
                                metadata={"title": item["title"]}
                            )
                            documents.append(doc)
            except json.JSONDecodeError as e:
                logging.error(f"JSON 디코딩 오류 발생: {filename} - {e}")
    return documents


def process_subfolder(subfolder_path, storage_context, embedding_model):
    documents = load_json_files(subfolder_path)
    index = VectorStoreIndex.from_documents(documents, storage_context=storage_context, embed_model=embedding_model, show_progress=True, insert_batch_size=65536)
    index.storage_context.persist(persist_dir=FLAGS.vector_store_dir)
    return storage_context

def main(argv):
    del argv

    if FLAGS.debug:
        logging.set_verbosity(logging.DEBUG)
    else:
        logging.set_verbosity(logging.INFO)
    

    embedding_model = RBLNBGEM3Embeddings(rbln_compiled_model_name=FLAGS.compiled_embedding_model)
    d = 1024
    M = 32
    faiss_index = faiss.IndexHNSWFlat(d, M)

    if FLAGS.load_from_storage:
        logging.debug('Loading from existing storage context...')
        # Should load all vector store, docstore, and index store
        # storage_context = StorageContext.from_defaults(persist_dir=FLAGS.vector_store_dir)
        vector_store = FaissVectorStore.from_persist_dir(FLAGS.vector_store_dir)
        doc_store = SimpleDocumentStore.from_persist_dir(FLAGS.vector_store_dir)
        index_store = SimpleIndexStore.from_persist_dir(FLAGS.vector_store_dir)
        storage_context = StorageContext.from_defaults(vector_store=vector_store, docstore=doc_store, index_store=index_store)
    else:
        logging.debug('Creating new storage context...')
        vector_store = FaissVectorStore(faiss_index=faiss_index)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # Process each subfolder
    data_dir = os.path.join(FLAGS.vector_store_dir, "json_merge")
    logging.debug(f'Opening directory {data_dir}')
    for subfolder in os.listdir(data_dir)+["./"]:
        subfolder_path = os.path.join(data_dir, subfolder)
        if os.path.isdir(subfolder_path):
            logging.info(f"Processing subfolder {subfolder}")
            vector_store = process_subfolder(subfolder_path, storage_context, embedding_model)

if __name__ == "__main__":
    app.run(main)