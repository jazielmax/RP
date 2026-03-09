import numpy as np
from rtlsdr import RtlSdr
from scipy.signal import decimate, firwin, lfilter

import sounddevice as sd



# reading is by default 2.4 MHZ

#Reading

sdr = RtlSdr()          # create SDR object
sdr.sample_rate = 2.4e6      # sample per second

sdr.gain = 'auto'           # higher = if signal weaker
                        # lower if signal is stronger

for i in range(0,1):
    print("Receiving samples...")
    sdr.center_freq = 105.3e6 + (i * 0.2e6)    # radio tuning
    samples = sdr.read_samples(sdr.sample_rate * 2 )  #2.4e6 samples read / 2.4e6 samples rate = 1 second
    #Interpretation
    print("Signal power:", np.mean(np.abs(samples)))

    # --- FM Demodulation ---
    nyq = sdr.sample_rate / 2
    cutoff = 200e3 # cutoff is related to bandwidth
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
frequencyDom = np.fft.fft(samples)

print(phase_diff.max())

sdr.close()
#look into rtl_power (sweeps data over wide frequency spectrum)



