import argparse
import logging
import os
import sys
import traceback
import threading
import uuid

from flask import Flask, request, jsonify, Response, stream_with_context
from llama_index.core import load_index_from_storage, StorageContext, Settings
from llama_index.vector_stores.faiss import FaissVectorStore
from llama_index.llms.openai_like import OpenAILike

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

    # Global dictionary to maintain chat engines per conversation_id
    chat_engine_dict = {}
    chat_engine_lock = threading.Lock()

    @flask_app.route('/query', methods=['POST'])
    def query():
        data = request.get_json()
        if not data or 'question' not in data:
            flask_app.logger.warning("No question provided in the request.")
            return jsonify({'error': 'No question provided'}), 400

        question = data.get('question')
        conversation_id = data.get('conversation_id')

        if not conversation_id:
            # Generate a new conversation_id
            conversation_id = str(uuid.uuid4())

        flask_app.logger.info(f"Received question: {question} for conversation_id: {conversation_id}")

        try:
            with chat_engine_lock:
                # Check if chat_engine exists for this conversation_id
                if conversation_id in chat_engine_dict:
                    chat_engine = chat_engine_dict[conversation_id]
                else:
                    # Create a new chat_engine and store it
                    chat_engine = index.as_chat_engine(
                        chat_mode="condense_plus_context",
                        context_prompt=(
                            "당신은 법률 관련 전문 지식을 보유한 대한민국의 법률 전문가이다."
                            "사용자가 제공한 질문을 바탕으로 핵심만 정확하게 답변하시오."
                            "\n참고 문서:\n{context_str}"
                            "참고 문서는 관련 없는 정보일 수 있다. 사용자의 질문에 벗어나는 법률이나 참고 문서는 반드시 제외하시오."
                        ),
                        streaming=True,
                        use_async=True,
                    )
                    chat_engine_dict[conversation_id] = chat_engine

            # Generate streaming response
            streaming_response = chat_engine.stream_chat(question)

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
