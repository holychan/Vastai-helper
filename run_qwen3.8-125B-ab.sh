#!/bin/bash
set -e
pip install toolong
cd /workspace

# Clone Strata
git clone https://github.com/Niko1221/Strata

# Download Qwen3.8 Flash Next Coder abliterated
hf download alesha-pro/Qwen3.8-Flash-Next-abliterated-GSQ-RCO-Coder-Strata-GGUF --local-dir coder
mv coder/mmproj-Qwen3.8-Flash-Next-BF16.gguf coder/IQ1_M/

cd Strata

# Define your custom arguments
FAMILY="coder"
GGUF_DIR="../coder/IQ1_M"
VISION="gpu"
CONTROL_VECTOR="../coder/Huihui-Qwen3.8-Flash-Next-refusal-direction-r.gguf"

echo "Executing unattended Strata configuration..."

# Use a Here-Doc (<<EOF) to automatically answer interactive prompts.
# Modify or add lines between EOF if the setup script asks for additional confirmations.
./setup.sh --setup \
  --family "$FAMILY" \
  --gguf-dir "$GGUF_DIR" \
  --vision "$VISION" \
  --port 18000 \
  --experimental-speed-projection "$CONTROL_VECTOR" <<EOF
1
6
1
y
n
EOF
# 1: IQ1_M quantized (only choice)
# 6: 262144 context length
# 1: 
# y: Run Calibrate (token rate is slow if not calibrated)
# n: Run Benchmark

#./setup.sh --help
#echo "Setup completed successfully. Starting the Python server..."

# Activate environment and start server automatically using your config
#source .venv/bin/activate
#python3 -m serve.server --engine strata --config strata-coder-iq1_m.json --port 18000
