#!/bin/bash
set -e
pip install toolong   # or huggingface_hub[cli] if you prefer
cd /workspace

# Clone Strata (keep as-is)
git clone https://github.com/Niko1221/Strata

# Download only the needed files from Huihui v2
hf download huihui-ai/Huihui-Qwen3.8-Flash-Next-abliterated-v2-GGUF \
  swift-IQ3_S/Swift-Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf \
  swift-IQ3_S/Swift-Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf \
  mmproj-Swift-Qwen3.8-Flash-Next-BF16.gguf \
  --local-dir model

# Move the projector into the quant folder (same pattern as before)
mv model/mmproj-Swift-Qwen3.8-Flash-Next-BF16.gguf model/swift-IQ3_S/

cd Strata

FAMILY="swift"                    # was "coder"
GGUF_DIR="../model/swift-IQ3_S"   # was "../coder/IQ1_M"
VISION="gpu"

echo "Executing unattended Strata configuration..."

./setup.sh --setup \
  --family "$FAMILY" \
  --gguf-dir "$GGUF_DIR" \
  --vision "$VISION" \
  --port 18000 \
  <<EOF
1
6
1
y
n
EOF
