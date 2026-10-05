# PROTOTYP (Erkennungs-Spike #60) – Wegwerf-Image, nicht der Erkennungsdienst.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cu130
RUN pip install --no-cache-dir transformers huggingface_hub safetensors ultralytics opencv-python-headless easyocr numpy pillow
ENV HF_HOME=/arbeit/hf YOLO_CONFIG_DIR=/arbeit/yolo EASYOCR_MODULE_PATH=/arbeit/easyocr
WORKDIR /spike
