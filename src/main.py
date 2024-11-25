import argparse
import logging
import os
import sys
import traceback

from flask import Flask, request, jsonify, Response, stream_with_context
from llama_index.core import load_index_from_storage, get_response_synthesizer, StorageContext, Settings
from llama_index.vector_stores.faiss import FaissVectorStore
from llama_index.llms.openai_like import OpenAILike
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.postprocessor import SimilarityPostprocessor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
from src.utils import RBLNBGEM3Embeddings

def parse_args():
    parser = argparse.ArgumentParser(description="Flask API Backend")
    parser.add_argument(
        "--vector_store_dir",
        type=str,
        default="data/rag",
        help="Directory to the vector store"
    )
    parser.add_argument(
        "--debug",
        action='store_true',
        help="Enable debug level logging"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to run the Flask app"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to run the Flask app"
    )
    return parser.parse_args()

def create_app(config):
    flask_app = Flask(__name__)

    # Configure logging
    if config.debug:
        flask_app.logger.setLevel(logging.DEBUG)
    else:
        flask_app.logger.setLevel(logging.INFO)

    # Set up the model and the large language model settings
    Settings.embed_model = RBLNBGEM3Embeddings(
        rbln_compiled_model_name="models/rbln_bge-m3_batch1_max8192",
    )
    Settings.llm = OpenAILike(
        model="models/rbln_vllm_EEVE-Korean-Instruct-10.8B-v1.0_npu8_batch1_max4096", 
        api_base="http://0.0.0.0:8000/v1", 
        api_key="byeonhophd_backend_980518", 
        max_tokens=1024, 
        is_chat_model=True  # Set this to apply chat template
    )

    # Set up the vector store and index
    vector_store = FaissVectorStore.from_persist_dir(config.vector_store_dir)
    storage_context = StorageContext.from_defaults(
        vector_store=vector_store, 
        persist_dir=config.vector_store_dir
    )
    index = load_index_from_storage(storage_context=storage_context)

    # Set up retriever
    retriever = VectorIndexRetriever(index=index, similarity_top_k=2)

    # Set up response synthesizer
    response_synthesizer = get_response_synthesizer(
        streaming=True,
        use_async=True
    )

    # Set up query engine
    query_engine = RetrieverQueryEngine(
        retriever=retriever,
        response_synthesizer=response_synthesizer,
        node_postprocessors=[SimilarityPostprocessor(similarity_cutoff=0.7)]
    )

    @flask_app.route('/query', methods=['POST'])
    def query():
        data = request.get_json()
        if not data or 'question' not in data:
            flask_app.logger.warning("No question provided in the request.")
            return jsonify({'error': 'No question provided'}), 400

        question = data.get('question')
        flask_app.logger.info(f"Received question: {question}")
        try:
            nodes = retriever.retrieve(question)

            # Generate streaming response
            streaming_response = query_engine.synthesize(
                question,
                nodes=nodes
            )

            def generate():
                for text in streaming_response.response_gen:
                    yield f"data: {text}\n\n"
                yield "data: [DONE]\n\n"

            return Response(stream_with_context(generate()), content_type='text/event-stream')
        except Exception as e:
            error_trace = traceback.format_exc()
            flask_app.logger.error(f"Error processing query: {str(e)}\n{error_trace}")
            return jsonify({'error': str(e), 'trace': error_trace}), 500

    return flask_app

def main():
    config = parse_args()
    app = create_app(config)
    app.run(host=config.host, port=config.port, debug=config.debug, use_reloader=False)

if __name__ == "__main__":
    main()
