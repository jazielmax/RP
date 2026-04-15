FROM python:3.9-slim

RUN apt-get update -y && apt-get upgrade -y && \
    apt-get install -y \
    build-essential \
    cmake \
    git \
    pkg-config \
    libusb-1.0-0-dev \
    gcc \
    ffmpeg \
    librtlsdr-dev \
    rtl-sdr \
    libasound-dev \
    portaudio19-dev \
    libportaudio2 \
    libportaudiocpp0 \
    postgresql \
    postgresql-contrib \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel

RUN python -m pip install --no-cache-dir \
    numpy scipy matplotlib pydub pyaudio \
    psycopg2-binary sounddevice pyrtlsdr

WORKDIR /code
COPY . /code