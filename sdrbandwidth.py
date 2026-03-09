import numpy as np
from rtlsdr import RtlSdr       #The RTL-SDR v4 uses Quadrature I/Q Sampling with 2.4mhz bandwidth
from scipy.signal import decimate, firwin, lfilter

import sounddevice as sd



#Configuration
sdr = RtlSdr()          #create SDR object
sdr.sample_rate = 2.4e6      #sample per second
sdr.center_freq = 100.7e6    #radio tuning          (frequency is 100.7e6 but the baseband is zero) its like taring a scale
sdr.gain = 'auto'           #higher = if signal stronger
                        #lower if signal is weaker


freq_increase = sdr.center_freq + 200_000
print("Receiving samples...")
samples = sdr.read_samples(2_400_000 * 1)  #2.4e6 samples read / 2.4e6 samples rate = 1 second
sdr.close()


print("Signal power:", np.mean(np.abs(samples))) #0.15 and greater is good, below 0.15 is weak

print("Computing FFT...")

fft_vals = np.fft.fft(samples)
freqs = np.fft.fftfreq(len(samples), d=1/sdr.sample_rate)

fft_vals = np.fft.fftshift(fft_vals)
freqs = np.fft.fftshift(freqs)

power_spectrum = np.abs(fft_vals)**2

total_energy = np.sum(power_spectrum)

cumulative_energy = np.cumsum(power_spectrum)

lower_index = np.where(cumulative_energy >= 0.025 * total_energy)[0][0]
upper_index = np.where(cumulative_energy >= 0.975 * total_energy)[0][0]

lower_freq = freqs[lower_index]
upper_freq = freqs[upper_index]

bandwidth = upper_freq - lower_freq

print("Lower frequency:", lower_freq)
print("Upper frequency:", upper_freq)
print("Estimated bandwidth:", bandwidth)
