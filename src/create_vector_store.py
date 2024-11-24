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

FLAGS = flags.FLAGS

os.environ["LLAMA_INDEX_CACHE_DIR"]="./tmp" # Designate LlamaIndex Cache directory


flags.DEFINE_string("vector_store_dir", "data/rag", "Directory to the vector store")
flags.DEFINE_string("compiled_embedding_model", "models/rbln_bge-m3_batch1_max8192", "Directory to compiled HuggingFace embedding model")
flags.DEFINE_bool("debug", True, "Enable debug level logging")
flags.DEFINE_bool("load_from_storage", False, "Load storage context from the storage")
flags.DEFINE_integer("chunk_size", 600, "Text chunk size")
flags.DEFINE_integer("chunk_overlap_size", 200, "Text chunk overlap size")

def process_subfolder(subfolder_path, storage_context, embedding_model):
    documents = SimpleDirectoryReader(subfolder_path).load_data()
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

    # Determine the embedding dimension
    embedding_test = embedding_model._get_text_embedding("This is a sample text.")

    faiss_index = faiss.IndexHNSWFlat(len(embedding_test), 32)

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