 # Sounddevice needs to be i contains sounddevice, pyrtlsdr contains librtlsdr
 # pyrtlsdr[lib] installs librlstd AND the WRAPPER pyrtlsdr (a variant built for OUR rtlsdr) 
FROM python:3.7
RUN apt-get update -y && apt-get upgrade -y && \
    apt-get install -y \
    librtlsdr-dev \
    rtl-sdr \
    gcc nano \
    ffmpeg libasound-dev portaudio19-dev libportaudio2 libportaudiocpp0 \ 
    postgresql postgresql-contrib 
RUN pip install numpy scipy matplotlib pydub pyaudio psycopg2 pyrtlsdr[lib] sounddevice
WORKDIR /code
