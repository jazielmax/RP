FROM python:3.9-slim

RUN apt-get update && apt-get install -y \
    git cmake build-essential libusb-1.0-0-dev pkg-config \
    ffmpeg gcc \
    libasound-dev portaudio19-dev libportaudio2 libportaudiocpp0 \
    postgresql postgresql-contrib \
    && rm -rf /var/lib/apt/lists/*

# Build latest RTL-SDR
RUN git clone https://github.com/librtlsdr/librtlsdr.git /rtl && \
    cd /rtl && mkdir build && cd build && \
    cmake .. && \
    make -j4 && \
    make install && \
    ldconfig

RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel

RUN python -m pip install --no-cache-dir \
    numpy scipy matplotlib pydub pyaudio \
    psycopg2-binary sounddevice pyrtlsdr mutagen fastapi \
    uvicorn sse-starlette soundfile

WORKDIR /code
COPY . /code
