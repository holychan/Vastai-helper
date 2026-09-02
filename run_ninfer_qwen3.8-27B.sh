#!/bin/bash
source /venv/main/bin/activate
pip install toolong

cd /workspace

git clone https://github.com/Neroued/ninfer.git
cd ninfer

apt-get update && apt-get install -y libavformat-dev libavcodec-dev libavutil-dev libswscale-dev

cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build -j

hf download neroued/Qwen3.8-27B-nvfp4-NInfer \
  qwen3_8_27b_nvfp4.ninfer \
  --local-dir models

./build/apps/ninfer-serve models/qwen3_8_27b_nvfp4.ninfer \
  --max-context 240000 \
  --kv-capacity 240000 \
  --max-concurrency 2 \
  --kv-dtype fp8 \
  --device-state-slots 2 \
  --host-state-slots 8 \
  --host-kv-mib 8192 \
  --spec mtp --draft-tokens 3 \
  --lm-head-draft \
  --preserve-thinking \
  --host 0.0.0.0 --port 18000 \
  --api-key sk-running-ai-model-opencode \
  --alias Qwen3.8-27B \
  --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0.0 \
  --presence-penalty 0.0 --repeat-penalty 1.0 \
  --preserve-thinking

