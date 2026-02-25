import numpy as np
from rtlsdr import RtlSdr
from scipy.signal import decimate, firwin, lfilter

import sounddevice as sd

#Configuration
sdr = RtlSdr()          #create SDR object
sdr.sample_rate = 2.4e6      #sample per second
sdr.center_freq = 100.7e6    #radio tuning
sdr.gain = 'auto'           #higher = if signal stronger
                        #lower if signal is weaker

print("Receiving samples...")
samples = sdr.read_samples(3_200_000 * 10)  #2.4e6 samples read / 2.4e6 samples rate = 1 second
sdr.close()


print("Signal power:", np.mean(np.abs(samples)))

# --- FM Demodulation ---
# Low-pass filter (200 kHz cutoff)
nyq = sdr.sample_rate / 2
cutoff = 200e3
taps = firwin(101, cutoff / nyq)

filtered = lfilter(taps, 1.0, samples)
print("Demodulating FM...")
phase_diff = np.angle(filtered[1:] * np.conj(filtered[:-1]))

# --- Downsample to audio rate ---
audio = decimate(phase_diff, 10)  # 2.4 MHz → 240 kHz
audio = decimate(audio, 5)        # 240 kHz → 48 kHz

# Normalize
audio /= np.max(np.abs(audio))

print("Playing audio...")
sd.play(audio, 48000)
sd.wait()

#"C:\Users\Jazz\AppData\Local\Programs\Python\Python314\Lib\site-packages\rtlsdr\__init__.py"

#NOTE
#look into rtl_power (sweeps data over wide frequency spectrum)
