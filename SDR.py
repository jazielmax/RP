import numpy as np
from rtlsdr import RtlSdr       #The RTL-SDR v4 uses Quadrature I/Q Sampling with 2.4mhz bandwidth
from scipy.signal import decimate, firwin, lfilter
import time

import sounddevice as sd


for i in range(1):
#Configuration
    sdr = RtlSdr()          #create SDR object
    sdr.sample_rate = 2.4e6      #sample per second
    sdr.center_freq = 100.7e6    #radio tuning          (frequency is 100.7e6 but the baseband is zero) its like taring a scale
    sdr.gain = 'auto'           #higher = if signal stronger
                            #lower if signal is weaker


    freq_increase = sdr.center_freq + 200_000
    print("Receiving samples...")
    start_time = time.time()
    samples = sdr.read_samples(2_400_000 * 5)  #2.4e6 samples read / 2.4e6 samples rate = 1 second
    sdr.close()
    end_time = time.time()

    elapsed_time = end_time - start_time
    print(elapsed_time)


    print("Signal power:", np.mean(np.abs(samples))) #0.15 and greater is good, below 0.15 is weak

# --- FM Demodulation ---
nyq = sdr.sample_rate / 2           #nyquist frequency
cutoff = 200e3                      #200khz bandwidth for each station
taps = firwin(101, cutoff / nyq) #filter length is 101 (how many previous samples are considered), normalized cutoff % (allow only frequencies from 0 to %) [taps is the weight on how much to emphasize each previous sample]

filtered_samples = lfilter(taps, 1.0, samples) #applies filter to the I/Q samples (divide by 1, meaning just use the numerator taps on samples)
print("Demodulating FM...")
phase_diff = np.angle(filtered_samples[1:] * np.conj(filtered_samples[:-1]))    # complex number = filtered[n] * conj(filtered[n-1]) and then angle(complex number) to extract the phase difference between samples (FM = rate of change of phase)
# think of it as a vector
# (I, Q) points a direction (represented as a complex number which represents positive AND negative frequencies in baseband)
# The angle of that vector is the phase (which shows where in the wave cycle the signal is)
# Length = amplitude (strength of signal)

# --- Downsample to audio rate ---
audio = decimate(phase_diff, 10)  # 2.4 MHz → 240 kHz       decimate applies low-pass filter + downsamples to avoid aliasing
audio = decimate(audio, 5)        # 240 kHz → 48 kHz        (48khz )

# Normalize
audio /= np.max(np.abs(audio))          #scales between -1 and 1 (volume reasons)

print("Playing audio...")
sd.play(audio, 48000)
sd.wait()


#fingerprinting
#audio -> time vs frequency (currently in amplitude v time) use short time fourier transform
#find STRONG frequency peaks (you'll have coordinate points of peaks)
#pair peaks together (don't store individual peaks, pair them together)
#hash those pairs
#store hashes in database (non relational database is KING (sqlite for local storage though))

#bad news have to build own hash database
#so essentially we have to create the hashes and store them
#which means we need LEGALLY OBTAIN music and create a script to hash them and store it into our cute database