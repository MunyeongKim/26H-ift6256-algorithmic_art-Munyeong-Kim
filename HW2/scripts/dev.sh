#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WHISPER_CPP_DIR="${WHISPER_CPP_DIR:-/tmp/whisper.cpp}"
WHISPER_BIN="${WHISPER_BIN:-$WHISPER_CPP_DIR/build/bin/whisper-server}"
WHISPER_MODEL="${WHISPER_MODEL:-}"
if [[ -z "$WHISPER_MODEL" ]]; then
  CANDIDATE_MODELS=(
    "ggml-small.en-q5_1.bin"
    "ggml-small.en.bin"
    "ggml-small.bin"
    "ggml-medium.en-q5_0.bin"
    "ggml-medium.en.bin"
    "ggml-medium.bin"
    "ggml-base.en.bin"
    "ggml-base.bin"
  )

  for MODEL_NAME in "${CANDIDATE_MODELS[@]}"; do
    MODEL_PATH="$WHISPER_CPP_DIR/models/$MODEL_NAME"
    if [[ -f "$MODEL_PATH" ]]; then
      WHISPER_MODEL="$MODEL_PATH"
      break
    fi
  done

  if [[ -z "$WHISPER_MODEL" ]]; then
    WHISPER_MODEL="$WHISPER_CPP_DIR/models/ggml-small.en-q5_1.bin"
  elif [[ "$(basename "$WHISPER_MODEL")" != "ggml-small.en-q5_1.bin" ]]; then
    echo "[dev] warning: ggml-small.en-q5_1.bin not found, using $(basename "$WHISPER_MODEL")" >&2
  fi
fi
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8080}"
WHISPER_THREADS="${WHISPER_THREADS:-8}"
WHISPER_CONVERT="${WHISPER_CONVERT:-1}"
WHISPER_TMP_DIR="${WHISPER_TMP_DIR:-/tmp}"

if [[ ! -x "$WHISPER_BIN" ]]; then
  echo "[dev] whisper-server not found or not executable: $WHISPER_BIN" >&2
  echo "[dev] Set WHISPER_BIN or WHISPER_CPP_DIR first." >&2
  exit 1
fi

if [[ ! -f "$WHISPER_MODEL" ]]; then
  echo "[dev] model file not found: $WHISPER_MODEL" >&2
  echo "[dev] Set WHISPER_MODEL to a valid ggml model path." >&2
  exit 1
fi

EXTRA_ARGS=()
if [[ "$WHISPER_CONVERT" == "1" || "$WHISPER_CONVERT" == "true" || "$WHISPER_CONVERT" == "TRUE" ]]; then
  if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "[dev] ffmpeg not found but WHISPER_CONVERT is enabled." >&2
    echo "[dev] Install ffmpeg or set WHISPER_CONVERT=0." >&2
    exit 1
  fi
  EXTRA_ARGS+=(--convert --tmp-dir "$WHISPER_TMP_DIR")
fi

echo "[dev] serving app + inference via whisper-server"
echo "[dev] public: $ROOT_DIR"
echo "[dev] model:  $WHISPER_MODEL"
echo "[dev] threads: $WHISPER_THREADS"
echo "[dev] open:   http://$HOST:$PORT"
if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
  echo "[dev] audio convert: enabled (ffmpeg)"
else
  echo "[dev] audio convert: disabled"
fi

exec "$WHISPER_BIN" \
  -m "$WHISPER_MODEL" \
  -t "$WHISPER_THREADS" \
  --host "$HOST" \
  --port "$PORT" \
  --public "$ROOT_DIR" \
  "${EXTRA_ARGS[@]}"
