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
   #gcc \
    ffmpeg \
    libasound-dev \
    portaudio19-dev \
    #libportaudio2 \
    #libportaudiocpp0 \
    postgresql \
    postgresql-contrib \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip setuptools wheel

# Install pyrtlsdr WITH its bundled librtlsdr
RUN pip install numpy scipy matplotlib pydub psycopg2-binary sounddevice
RUN pip install pyrtlsdr[lib]
#pyaudio
WORKDIR /code
COPY . /code



# This was the old settings 
#FROM python:3.7
#RUN apt-get update -y && apt-get upgrade -y && \
#   apt-get install -y \
#   librtlsdr-dev \
#   rtl-sdr \
#    gcc nano \
#    ffmpeg libasound-dev portaudio19-dev libportaudio2 libportaudiocpp0 \ 
#    postgresql postgresql-contrib 
#RUN pip install numpy scipy matplotlib pydub pyaudio psycopg2 pyrtlsdr[lib] sounddevice
#WORKDIR /code
