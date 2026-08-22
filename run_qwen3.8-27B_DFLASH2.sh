#!/bin/bash
source /venv/main/bin/activate
pip install toolong

cd /workspace
wget https://github.com/holychan/Vastai-helper/raw/refs/heads/main/beellama_compiled_dist.tar.gz 
tar -xzvf  beellama_compiled_dist.tar.gz 
cd bin && export LD_LIBRARY_PATH=$(pwd):$LD_LIBRARY_PATH

./llama-server -hf utautako/Qwen3.8-27B-NVFP4-MTP-Q8attn-GGUF \
  -hfd z-lab/Qwen3.8-27B-DFlash2-GGUF:Q4_K_M \
  --spec-type draft-dflash \
  --spec-draft-n-max 6 \
  --spec-draft-p-min 0.6 \
  -ngl all \
  --spec-draft-ngl all \
  --threads 16 \
  --threads-batch 16 \
  -c 213056 \
  --kv-unified \
  --jinja \
  --cache-type-k q8_0 --cache-type-v q8_0 \
  -np 1 -fa on \
  -b 2048 -ub 512 \
  --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0.0 \
  --presence-penalty 0.0 --repeat-penalty 1.0 \
  --alias Qwen3.8-27B \
  --reasoning on --reasoning-preserve --reasoning-format deepseek --reasoning-budget 16000 \
  --checkpoint-min-step 4096 --ctx-checkpoints 64 \
  --perf --metrics \
  --host 0.0.0.0 --port 18000 \
  --api-key sk-running-ai-model-opencode 
