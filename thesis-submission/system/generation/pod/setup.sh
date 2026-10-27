#!/bin/bash
# ref: phase4.1. one-shot rebuild of spar3d + sdxl services on a fresh runpod pod.
# run this after: (1) runpod-backup-v2.tar.gz is at /workspace/runpod-backup-v2.tar.gz
#                  (2) sdxl_wrapper.py is at /workspace/sdxl_wrapper.py
# usage: bash /workspace/setup.sh
set -e

echo "=== Tangible Worlds pod setup starting ==="

# 0. persistent env var so HF weights always land on /workspace, not root disk.
# written to .bashrc so future shells on THIS pod's lifetime have it automatically.
# (still gets wiped on the next full reset, this script re-adds it every run, harmless if already there)
grep -qxF 'export HF_HOME=/workspace/hf-cache' ~/.bashrc || echo 'export HF_HOME=/workspace/hf-cache' >> ~/.bashrc
export HF_HOME=/workspace/hf-cache
mkdir -p "$HF_HOME"

# 1. restore + install SPAR3D (system python, matches the proven working setup, no venv)
if [ ! -d ~/workspace/stable-point-aware-3d ]; then
  echo "--- restoring SPAR3D code from /workspace/runpod-backup-v2.tar.gz ---"
  mkdir -p ~/workspace
  if [ ! -f /workspace/runpod-backup-v2.tar.gz ]; then
    echo "!!! ERROR: /workspace/runpod-backup-v2.tar.gz not found. Send it up first with runpodctl."
    exit 1
  fi
  tar -xzf /workspace/runpod-backup-v2.tar.gz -C ~/workspace
else
  echo "--- SPAR3D code already present, skipping restore ---"
fi

echo "--- installing SPAR3D dependencies (system python) ---"
cd ~/workspace/stable-point-aware-3d
pip install --no-cache-dir -r requirements.txt --no-build-isolation
pip install --no-cache-dir flet==0.21.2
pip install --no-cache-dir --ignore-installed blinker flask

# 2. SDXL venv (isolated from SPAR3D, lives on root disk since /workspace is too slow for venv symlinks)
if [ ! -d ~/workspace/sdxl-env ]; then
  echo "--- creating SDXL venv ---"
  python3 -m venv ~/workspace/sdxl-env
fi
echo "--- installing SDXL dependencies ---"
source ~/workspace/sdxl-env/bin/activate
pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cu118
pip install --no-cache-dir diffusers transformers accelerate flask
deactivate

# 3. sanity check the wrapper script made it up
if [ ! -f /workspace/sdxl_wrapper.py ]; then
  echo "!!! WARNING: /workspace/sdxl_wrapper.py not found. Send it up before starting the SDXL service."
else
  echo "--- sdxl_wrapper.py found on /workspace, good ---"
fi

echo ""
echo "=== setup complete ==="
echo "to run SPAR3D (terminal 1):"
echo "  cd ~/workspace/stable-point-aware-3d && python wrapper.py"
echo ""
echo "to run SDXL (terminal 2):"
echo "  source ~/workspace/sdxl-env/bin/activate && python /workspace/sdxl_wrapper.py"
