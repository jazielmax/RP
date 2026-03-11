import numpy as np
from rtlsdr import RtlSdr
from scipy.signal import decimate, firwin, lfilter
import matplotlib.pyplot as plt # used for pysdr example code
import sounddevice as sd

# Note: Power peaks may not denote a strong signal, as they can be short lived, it is also necessary to measure the width of the signal, as it should be close to the bandwidth of FM radio (200,000hz)


threshholdForSignal = 1e6 # a global for now just to allow quick playing around (This is a very low threshold, I see most strong signals go to 1e7)
def convertRelativeFrequencyToActual(centralFreq, sampleRate, indexInSample): # Given the location a desired frequency is on a sample ndArray, returns the actual frequency value that the signal is located at, as a sample is normally formatted in realativity to the central frequency
    return

def findCenterOfSignal(i): # Given the starting loation of a signal, traverses the signal till it finds the peak. I will return the end of the signal, so we make sure to not count the same signal twice
    return # think of adding a size constraint, as size should be around 2e3 to be considered an fm signal

def findStrongSignals(FrequencyDomainPower: np.ndarray): # Given a frequency domain sample already set for power, returns the frequencies where the center of strong signals are
    ans = [] # will hold a list frequencies
    for i in range(0, len(FrequencyDomainPower)):
        if(np.log10(FrequencyDomainPower[i]) > threshholdForSignal):
            ans.append(findCenterOfSignal(i))
def main():
    # reading is by default 2.4 MHZ

    #Reading

    sdr = RtlSdr()          # create SDR object
    sdr.sample_rate = 2.56e6      # sample per second

    sdr.gain = 'auto'           # higher = if signal weaker
                            # lower if signal is stronger

    for i in range(0,1):
        print("Receiving samples...")
        #sdr.center_freq = 96.1e6 + (i * 2.56e6 )    # radio tuning i * 0.2e3
        sdr.center_freq = 103.5e6 + (i * 2.56e6 )  
        samples = sdr.read_samples(sdr.sample_rate * 1 )  #2.4e6 samples read / 2.4e6 samples rate = 1 second
        #Interpretation
        print("Signal power:", np.mean(np.abs(samples) ** 2))

        # --- FM Demodulation ---
        nyq = sdr.sample_rate / 2
        cutoff = 200e3 # cutoff is related to bandwidth
        taps = firwin(101, cutoff / nyq) #filter length is 101, cutoff is 200khz (how FM bandwith works), normalized
    
        filtered = lfilter(taps, 1.0, samples) #applies filter 
        print("Demodulating FM...")
        phase_diff = np.angle(filtered[1:] * np.conj(filtered[:-1]))    #actually demodulates (data stored in frequency)

        powerAtGivenHzOfBandwidth = (np.abs(samples)) ** 2 # power is a better measure for finding stations (as phase_diff can sometiems not change radically on a real station)

        #centerI = int(sdr.sample_rate / 2)
        #print("Power at curr Signal", powerAtGivenHzOfBandwidth[centerI])




        # --- Downsample to audio rate ---
        audio = decimate(phase_diff, 10)  # 2.4 MHz → 240 kHz
        audio = decimate(audio, 5)        # 240 kHz → 48 kHz        (48khz )

        # Normalize
        audio /= np.max(np.abs(audio))          #scales between -1 and 1 (volume reasons)

        print("Playing audio...")
        sd.play(audio, 48000)
        sd.wait() 
        
        frequencyDom = np.fft.fftshift(np.fft.fft(samples))   # turns samples from time domain to frequency domain (what we want). 
        #We have to do a shift any time we do FFT (fast fourier transfer) as it outputs from Greatest to least, but we want lowest to heighest frequencies with 0 in the middle. This makes the center frequency located at 0 and allows us to determinine at what hz the frequencies are in relation to the central frequency
        powerArrInFrequencyDom = np.abs(frequencyDom) ** 2 # used to get power of frequency domaind
        centerIdxInSample = len(powerArrInFrequencyDom) // 2
        print("Power at curr Signal", powerArrInFrequencyDom[centerIdxInSample]) # returns the power at the central frequency (currently set to be a strong signal)




         
        ######### CODE TAKEN FROM PYSDR.org#######################
        Fs = 1 # Hz   
        t = np.arange(sdr.sample_rate) # because our sample rate is 1 Hz
        #s = np.sin(0.15*2*np.pi*t)
        S_mag = np.abs(frequencyDom) ** 2 # gives us power for the y axis
        S_phase = np.angle(frequencyDom)
        f = np.arange(Fs/-2, Fs/2, Fs/sdr.sample_rate)
        plt.figure(0)
        plt.plot(f, S_mag,'.-')
        plt.figure(1)
        plt.plot(f, S_phase,'.-')
        plt.show()
        ########################################################## 
    



        # note that with fast fourier transfer, power grows by amplitude ^ 2 * n (number of samples!) So our measurement must stick to one specific sample rate, or else our code wont work

    sdr.close()
    #look into rtl_power (sweeps data over wide frequency spectrum)

if __name__ == "__main__":
    main()

