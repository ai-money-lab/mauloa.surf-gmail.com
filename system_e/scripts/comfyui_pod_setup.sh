#!/bin/bash
# =============================================================================
# ComfyUI GPU Pod Auto-Setup Script
# =============================================================================
# RunPod GPU Podの初回起動時にComfyUIとFlux.1 Devモデルを自動セットアップ
#
# 前提条件:
#   - RunPod GPU Pod（Volume Disk 75GB以上）
#   - Python 3.10+
#
# 使い方:
#   curl -sSL <raw_url> | bash
#   または Pod内で: bash comfyui_pod_setup.sh
# =============================================================================

set -euo pipefail

# --- Configuration ---
WORKSPACE="/workspace"
COMFYUI_DIR="${WORKSPACE}/ComfyUI"
MODELS_DIR="${COMFYUI_DIR}/models"
CHECKPOINTS_DIR="${MODELS_DIR}/checkpoints"
CLIP_DIR="${MODELS_DIR}/clip"
VAE_DIR="${MODELS_DIR}/vae"
FLUX_MODELS_DIR="${WORKSPACE}/flux_models"
MIN_DISK_GB=25  # Minimum free space needed for model download

# Model URLs (Hugging Face - Comfy-Org official)
FLUX_CHECKPOINT_URL="https://huggingface.co/Comfy-Org/flux1-dev/resolve/main/flux1-dev-fp8.safetensors"
FLUX_CHECKPOINT_FILE="flux1-dev-fp8.safetensors"

# --- Helper Functions ---
log() { echo "[$(date '+%H:%M:%S')] $*"; }
error() { echo "[$(date '+%H:%M:%S')] ERROR: $*" >&2; }

check_disk_space() {
    local avail_gb
    avail_gb=$(df --output=avail -BG "${WORKSPACE}" | tail -1 | tr -d ' G')
    log "Disk space available: ${avail_gb}GB"
    if [ "${avail_gb}" -lt "${MIN_DISK_GB}" ]; then
        error "Insufficient disk space: ${avail_gb}GB available, need ${MIN_DISK_GB}GB+"
        error "Please expand your RunPod Volume Disk to 75GB or more."
        exit 1
    fi
}

# --- Step 1: Install ComfyUI ---
install_comfyui() {
    if [ -d "${COMFYUI_DIR}" ] && [ -f "${COMFYUI_DIR}/main.py" ]; then
        log "ComfyUI already installed at ${COMFYUI_DIR}"
        cd "${COMFYUI_DIR}" && git pull --ff-only 2>/dev/null || true
        return
    fi
    log "Installing ComfyUI..."
    cd "${WORKSPACE}"
    git clone https://github.com/comfyanonymous/ComfyUI.git
    cd "${COMFYUI_DIR}"
    pip install -r requirements.txt -q
    log "ComfyUI installed successfully"
}

# --- Step 2: Create model directories ---
setup_model_dirs() {
    log "Setting up model directories..."
    mkdir -p "${CHECKPOINTS_DIR}" "${CLIP_DIR}" "${VAE_DIR}"
}

# --- Step 3: Link or move existing flux_models ---
link_existing_models() {
    if [ ! -d "${FLUX_MODELS_DIR}" ]; then
        log "No existing flux_models directory found, skipping symlinks"
        return
    fi

    log "Linking existing flux_models to ComfyUI directories..."

    # VAE: ae.safetensors
    if [ -f "${FLUX_MODELS_DIR}/ae.safetensors" ] && [ ! -e "${VAE_DIR}/ae.safetensors" ]; then
        ln -sf "${FLUX_MODELS_DIR}/ae.safetensors" "${VAE_DIR}/ae.safetensors"
        log "  Linked ae.safetensors -> vae/"
    fi

    # CLIP: clip_l.safetensors
    if [ -f "${FLUX_MODELS_DIR}/clip_l.safetensors" ] && [ ! -e "${CLIP_DIR}/clip_l.safetensors" ]; then
        ln -sf "${FLUX_MODELS_DIR}/clip_l.safetensors" "${CLIP_DIR}/clip_l.safetensors"
        log "  Linked clip_l.safetensors -> clip/"
    fi

    # T5: t5xxl_fp8_e4m3fn.safetensors
    if [ -f "${FLUX_MODELS_DIR}/t5xxl_fp8_e4m3fn.safetensors" ] && [ ! -e "${CLIP_DIR}/t5xxl_fp8_e4m3fn.safetensors" ]; then
        ln -sf "${FLUX_MODELS_DIR}/t5xxl_fp8_e4m3fn.safetensors" "${CLIP_DIR}/t5xxl_fp8_e4m3fn.safetensors"
        log "  Linked t5xxl_fp8_e4m3fn.safetensors -> clip/"
    fi
}

# --- Step 4: Download Flux.1 Dev FP8 checkpoint ---
download_flux_checkpoint() {
    local target="${CHECKPOINTS_DIR}/${FLUX_CHECKPOINT_FILE}"

    if [ -f "${target}" ]; then
        local size_gb
        size_gb=$(du -BG "${target}" | cut -f1 | tr -d 'G')
        if [ "${size_gb}" -ge 15 ]; then
            log "Flux checkpoint already exists (${size_gb}GB), skipping download"
            return
        fi
        log "Incomplete checkpoint found (${size_gb}GB), re-downloading..."
        rm -f "${target}"
    fi

    check_disk_space

    log "Downloading Flux.1 Dev FP8 checkpoint (~16GB)..."
    log "This will take a few minutes depending on network speed..."

    # Use wget with resume support
    wget -c -O "${target}" "${FLUX_CHECKPOINT_URL}" 2>&1 | \
        grep --line-buffered -E '^\s*[0-9]+%|Saving to|Length:' || true

    if [ -f "${target}" ]; then
        local final_size
        final_size=$(du -h "${target}" | cut -f1)
        log "Checkpoint downloaded successfully: ${final_size}"
    else
        error "Checkpoint download failed!"
        exit 1
    fi
}

# --- Step 5: Install custom nodes (optional) ---
install_custom_nodes() {
    local custom_nodes_dir="${COMFYUI_DIR}/custom_nodes"
    mkdir -p "${custom_nodes_dir}"

    # ComfyUI Manager (useful for managing nodes)
    if [ ! -d "${custom_nodes_dir}/ComfyUI-Manager" ]; then
        log "Installing ComfyUI Manager..."
        cd "${custom_nodes_dir}"
        git clone https://github.com/ltdrdata/ComfyUI-Manager.git 2>/dev/null || true
    fi
}

# --- Step 6: Start ComfyUI ---
start_comfyui() {
    log "Starting ComfyUI on port 8188..."
    cd "${COMFYUI_DIR}"

    # Kill any existing ComfyUI process
    pkill -f "python.*main.py.*--listen" 2>/dev/null || true
    sleep 1

    # Start in background with GPU
    nohup python main.py \
        --listen 0.0.0.0 \
        --port 8188 \
        --preview-method auto \
        > "${WORKSPACE}/comfyui.log" 2>&1 &

    local pid=$!
    log "ComfyUI started (PID: ${pid})"
    log "Log: ${WORKSPACE}/comfyui.log"

    # Wait for ComfyUI to be ready
    log "Waiting for ComfyUI to load models..."
    local max_wait=120
    local waited=0
    while [ ${waited} -lt ${max_wait} ]; do
        if curl -s http://localhost:8188/system_stats > /dev/null 2>&1; then
            log "ComfyUI is ready!"
            return
        fi
        sleep 3
        waited=$((waited + 3))
    done

    error "ComfyUI did not start within ${max_wait}s. Check ${WORKSPACE}/comfyui.log"
    tail -20 "${WORKSPACE}/comfyui.log"
    exit 1
}

# --- Main ---
main() {
    log "========================================="
    log "ComfyUI + Flux.1 Dev Auto-Setup"
    log "========================================="

    install_comfyui
    setup_model_dirs
    link_existing_models
    download_flux_checkpoint
    install_custom_nodes
    start_comfyui

    log "========================================="
    log "Setup complete!"
    log "ComfyUI URL: https://<POD_ID>-8188.proxy.runpod.net"
    log "========================================="

    # Show final disk usage
    df -h "${WORKSPACE}"
    echo ""
    log "Model files:"
    ls -lh "${CHECKPOINTS_DIR}/" 2>/dev/null || true
}

main "$@"
