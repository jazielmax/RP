FROM python:3.9-slim

# Install ONLY what's needed for your application (no librtlsdr system packages)
RUN apt-get update -y && apt-get upgrade -y && \
    apt-get install -y \
    ## pulseaudio is for WSL ONLY
    pulseaudio \
    pulseaudio-utils \
    build-essential \
    cmake \
    git \
    pkg-config \
    libusb-1.0-0-dev \
    gcc \
    ffmpeg \
    libasound-dev \
    portaudio19-dev \
    libportaudio2 \
    libportaudiocpp0 \
    postgresql \
    postgresql-contrib \
    && rm -rf /var/lib/apt/lists/*

#ENV PYTHONDONTWRITEBYTECODE=1
#ENV PYTHONUNBUFFERED=1

RUN pip install --upgrade pip setuptools wheel

# Install pyrtlsdr WITH its bundled librtlsdr
RUN pip install numpy scipy matplotlib pydub pyaudio psycopg2-binary sounddevice
RUN pip install pyrtlsdr[lib]

ENV RTLSDR_ZEROCOPY=0

WORKDIR /code
COPY . /code

