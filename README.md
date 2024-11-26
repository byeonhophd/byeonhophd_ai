# Lawgenda AI (by ByeonhoPhd)

## Introduction
Main modeling code of Lawgenda. This repository containes all ML lifecycle including model serving code of Lawgenda service.

## Usage
1. Install dependencies

```bash
pip install -i https://pypi.rbln.ai/simple rebel-compiler optimum-rbln vllm-rbln
pip install -r requirements.txt
```

2. Prepare FAISS vector store from documents

This will process your documents and create a FAISS vector store with HNSW indexing.

```bash
python src/compile_bge.py
python create_vector_store.py
```

3. Instantiate vllm endpoint & Run

This will compile model and start the Flask API server.

```bash
python compile_eeve.py
sh run_vllm.sh
```
