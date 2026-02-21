# Whisper Real-Time Setup (Local, No Token)

This project expects `whisper.cpp` server at `POST /inference`.

## 1) Build whisper.cpp on Apple Silicon

```bash
cd /tmp
git clone https://github.com/ggml-org/whisper.cpp.git
cd whisper.cpp
brew install cmake ffmpeg
cmake -B build -DWHISPER_METAL=ON
cmake --build build -j
```

## 2) Download a model

- English only (faster): `ggml-base.en.bin`
- Multilingual (includes Korean): `ggml-base.bin` or `ggml-small.bin`

```bash
cd /tmp/whisper.cpp
bash ./models/download-ggml-model.sh base
```

## 3) Run whisper-server with this HW2_2 folder as `--public`

```bash
cd /tmp/whisper.cpp
./build/bin/whisper-server \
  -m ./models/ggml-base.bin \
  --host 127.0.0.1 \
  --port 8080 \
  --convert \
  --public "/Users/KimMunyeong/Github/algorithmic art/HW2_2"
```

## 3-b) One-command dev run (`npm run dev`)

```bash
cd "/Users/KimMunyeong/Github/algorithmic art/HW2_2"
npm run dev
```

The script defaults to:
- `WHISPER_CPP_DIR=/tmp/whisper.cpp`
- `WHISPER_MODEL=/tmp/whisper.cpp/models/ggml-base.bin`

Override if needed:

```bash
cd "/Users/KimMunyeong/Github/algorithmic art/HW2_2"
WHISPER_CPP_DIR="$HOME/whisper.cpp" \
WHISPER_MODEL="$HOME/whisper.cpp/models/ggml-base.bin" \
npm run dev
```

## 4) Open app

Open:

```text
http://127.0.0.1:8080
```

Then click `Start Mic` in the UI.

Notes:
- Browser mic permission is required.
- This app sends short `webm/mp4` audio chunks to local `/inference` and appends returned transcript.
- Keep `--convert` enabled so whisper-server transcodes chunks to WAV via ffmpeg.
- For lower latency, use smaller model (`base` / `tiny`).
