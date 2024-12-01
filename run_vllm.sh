nohup python -m vllm.entrypoints.openai.api_server \
             --model models/rbln_vllm_EEVE-Korean-Instruct-10.8B-v1.0_npu8_batch1_max4096 \
             --compiled-model-dir models/rbln_vllm_EEVE-Korean-Instruct-10.8B-v1.0_npu8_batch1_max4096 \
             --dtype auto \
             --device rbln \
             --max-num-seqs 1 \
             --max-num-batched-tokens 4096 \
             --max-model-len 4096 \
             --block-size 4096 \
             --api-key byeonhophd_backend_980518 \
             &


python src/main.py