import numpy as np
from rtlsdr import RtlSdr
from scipy.signal import decimate, firwin, lfilter
import time

import sounddevice as sd

#already get a 2.4mhz bandwith (it just gets cut off later in demodulation)
#
for i in range(3):
#Configuration
    sdr = RtlSdr()          #create SDR object
    sdr.sample_rate = 2.4e6      #sample per second
    sdr.center_freq = 100.7e6    #radio tuning
    sdr.gain = 'auto'           #higher = if signal stronger
                            #lower if signal is weaker


    freq_increase = sdr.center_freq + 200_000
    print("Receiving samples...")
    start_time = time.time()
    samples = sdr.read_samples(2_400_000 * 0.25)  #2.4e6 samples read / 2.4e6 samples rate = 1 second
    sdr.close()
    end_time = time.time()

    elapsed_time = end_time - start_time
    print(elapsed_time)


    print("Signal power:", np.mean(np.abs(samples)))

# --- FM Demodulation ---
nyq = sdr.sample_rate / 2
cutoff = 200e3
taps = firwin(101, cutoff / nyq) #filter length is 101, cutoff is 200khz (how FM bandwith works), normalized

filtered = lfilter(taps, 1.0, samples) #applies filter 
print("Demodulating FM...")
phase_diff = np.angle(filtered[1:] * np.conj(filtered[:-1]))    #actually demodulates (data stored in frequency)

# --- Downsample to audio rate ---
audio = decimate(phase_diff, 10)  # 2.4 MHz → 240 kHz
audio = decimate(audio, 5)        # 240 kHz → 48 kHz        (48khz )

# Normalize
audio /= np.max(np.abs(audio))          #scales between -1 and 1 (volume reasons)

print("Playing audio...")
sd.play(audio, 48000)
sd.wait()

#"C:\Users\Jazz\AppData\Local\Programs\Python\Python314\Lib\site-packages\rtlsdr\__init__.py"


#look into rtl_power (sweeps data over wide frequency spectrum)
#not useful for pipeline but it can detect active frequencies (can scan for strong signals in dB over frequency range)
#can automatically discover stations in a new area

#fingerprinting
#audio -> time vs frequency (currently in amplitude v time) use short time fourier transform
#find STRONG frequency peaks (you'll have coordinate points of peaks)
#pair peaks together (don't store individual peaks, pair them together)
#hash those pairs
#store hashes in database (non relational database is KING (sqlite for local storage though))

#bad news have to build own hash database
#so essentially we have to create the hashes and store them
#which means we need LEGALLY OBTAIN music and create a script to hash them and store it into our cute database