import numpy as np
from rtlsdr import RtlSdr
from scipy.signal import decimate, firwin, lfilter
import matplotlib.pyplot as plt # used for pysdr example code
import sounddevice as sd

#Note that we need to use np.array SAMPLES not the fft (frequency domain) , 
#-6.9e4 6.972e4 = 138,720, with threshold of 48 maybe we use a width of 100,000? set the cap to 200,000 to avoid interference
# Now we need to calculate relativity! This was done with an estimated floor of 24.488740585217858 dbs
#Noise at 23, desired signal at 43-60 (do note I've found signals also at 43 but peak at 55, and they are not strong signals/should not be considered)

#proposed threshold:  23.5112594148 + the noise (note that I use PLUS not multiply as you should not use multiplication or divison with db's, so the realativity is just the threshold - floor)
# proposed width: 100,000

#Current plan for signal detection:
# 1. Estimate noise floor value
# 2. Calculate relative threshold to deem a possible signal
# 3. LOOK INTO Run the scipy correlate function on a possible signal with a hardcoded strong signal, and accept the signal as strong for a constant confidence value (maybe like 0.4-0.6 confidence). Use frequency
# possibly use mode = 'fft'
#4: Once you have a list of prospective signals, use a RMS (root mean square) threshold (must be relative to floor!) to guarantee all signals have no static noise

# Note: Power peaks may not denote a strong signal, as they can be short lived, it is also necessary to measure the width of the signal, as it should be close to the bandwidth of FM radio (200,000hz)
# LOOK INTO CONVERTING POWER IN FREQUENCY DOMAIN (X AXIS IS FREQUENCY) TO DB'S (decibels)

threshholdForSignal = -1 # a global for now just to allow quick playing around (This is a very low threshold, I see most strong signals go to 1e7)
thresholdForWidth = -1
def convertRelativeFrequencyToActual(centralFreq, targetRelativeFrequency): # Given the location a desired frequency is on a sample ndArray, returns the actual frequency value that the signal is located at, as a sample is normally formatted in realativity to the central frequency
    return centralFreq + targetRelativeFrequency # targetFrequency should be relative, as the value is its distance from the central frequency, thats why this simple formula works

def findCenterOfSignal(representationOfFrequencies, i): # Given the starting loation of a signal, traverses the signal till it finds the peak. I will return the end of the signal, so we make sure to not count the same signal twice
    startI = i
    max = -1
    maxI = -1
    sampleLength = len(representationOfFrequencies)
    while True: #Just a goofy do while-like to allow repOfFreq to be a var (condenses code)
        currYVal = representationOfFrequencies[i]
        if currYVal < threshholdForSignal or i >= sampleLength: 
            i-=1 #If here, it means the i before it was the last frequency of signal
            break #case to end while
        if currYVal > max: 
            max = currYVal
            maxI = i # the location of the highest recorded peak
        i+=1
    #Note that the maxI value that is returned is stored as a relative frequency, as it it states how far away it is from the central frequency. This must be converted (though the convertRelativeFrequencyToActual) in order for it to be useful
    return (maxI, i - startI) #left is the center frequencies's location, right is the width of the signal (as i is the end index, startI is the start)
#representationOfFrequencies[i] > threshholdForSignal and i < sampleLength

def findStrongSignals(centralFreq, representationOfFrequencies: np.ndarray): # Given a frequency domain sample already set for power, returns the frequencies where the center of strong signals are
    ans = [] # will hold a list frequencies
    samplelength = len(representationOfFrequencies)
    centerI = -1
    width = -1
    i = 0
    while i < samplelength: 
        if(representationOfFrequencies[i] >= threshholdForSignal):
            centerI, width = findCenterOfSignal(i)
            if width > thresholdForWidth:
                ans.append(convertRelativeFrequencyToActual(centralFreq, centerI))
def main():
    # reading is by default 2.4 MHZ

    #Reading

    sdr = RtlSdr()          # create SDR object
    sdr.sample_rate = 2.56e6      # sample per second

    sdr.gain = 'auto'           # higher = if signal weaker
                            # lower if signal is stronger

    for i in range(0,1):
        print("Receiving samples...")
        #sdr.center_freq = 101.7e6 + (i * 2.56e6 )   # Strong signal  radio tuning i * 0.2e3
        #sdr.center_freq = 104.10e6 + (i * 2.56e6 )  # VERY GOOD SIGNAL FOR WEAKEST STRONG SIGNALS
        sdr.center_freq = 106.5e6
        #sdr.center_freq = 101.5e6 CASE WITH A LOT OF INTERFERING SIGNALS
        #sdr.center_freq = 94.7e6 Signal that is too weak/we dont want this to be counted!
        samples = sdr.read_samples(sdr.sample_rate * 2 )  #2.4e6 samples read / 2.4e6 samples rate = 1 second
        #Interpretation
        print("Signal power:", np.mean(np.abs(samples) ** 2))

        # --- FM Demodulation ---
        nyq = sdr.sample_rate / 2
        cutoff = 200e3 # cutoff is related to bandwidth
        taps = firwin(101, cutoff / nyq) #filter length is 101, cutoff is 200khz (how FM bandwith works), normalized
    
        filtered = lfilter(taps, 1.0, samples) #applies filter 
        print("Demodulating FM...")
        phase_diff = np.angle(filtered[1:] * np.conj(filtered[:-1]))    #actually demodulates (data stored in frequency)

        #powerAtGivenHzOfBandwidth = (np.abs(samples)) ** 2 # power is a better measure for finding stations (as phase_diff can sometiems not change radically on a real station)

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
        



        # signal detection code 
        frequencyDom = np.fft.fftshift(np.fft.fft(samples))   # turns samples from time domain to frequency domain (what we want). 
        powerFreqDom = np.abs(frequencyDom) ** 2
        #We have to do a shift any time we do FFT (fast fourier transfer) as it outputs from Greatest to least, but we want lowest to heighest frequencies with 0 in the middle. This makes the center frequency located at 0 and allows us to determinine at what hz the frequencies are in relation to the central frequency
        #powerArrInFrequencyDom = np.abs(frequencyDom) ** 2 # used to get power of frequency domaind
        db = 10 * np.log10(powerFreqDom + 1e-12) # adding a very small amount ensures we do not do log10(0) which in matplotlib shows an empty/null value
        
        relativeThreshold = 23.5112594148 # distance from the floor that we consider a strong signal
        floorEstimate = np.average(np.percentile(db, 15)) # noise estimate
        strongSignalThreshold = floorEstimate + relativeThreshold
        # Just a reminder, fftshift makes the central frequency located at n/2 (size of samples / 2)
        rms =  np.sqrt(np.mean(np.square(samples)))# Root mean square is used to find how much noise is in a signal. IMPORANT: RMS MUST BE CALCULATED FROM TIME DOMAIN
        print ("Guess of noise: " + str(floorEstimate) + "\nProposed threshold: " + str(strongSignalThreshold))
        #centerIdxInSample = len(DbFS) // 2
        #print("Power at curr Signal", DbFS[centerIdxInSample]) # returns the power at the central frequency (currently set to be a strong signal)

        #TODO:  NEED TO LEARN HOW TO EXTRACT A SINGLE SIGNAL FROM THE TIME DOMAIN (SAMPLE ARRAY)



         
        ######### CODE TAKEN FROM PYSDR.org#######################
        Fs = 1 # Hz   
        S_mag = db# gives us power for the y axis
        #f = np.arange(sdr.sample_rate/-2, sdr.sample_rate/2, Fs) # now x axis is in terms of bandwidth Hz. np.arrange works like this: 1st param is start, 2nd param is stop, 3rd param is step size of graph (1 is preferred in this case)
        f = f = np.linspace(sdr.sample_rate/-2, sdr.sample_rate/2, num=db.size)
        plt.plot(f, S_mag,'.-')
        plt.show()
        ########################################################## 
    


        # note that with fast fourier transfer, power grows by amplitude ^ 2 * n (number of samples!) So our measurement must stick to one specific sample rate, or else our code wont work

    sdr.close()
    #look into rtl_power (sweeps data over wide frequency spectrum)

if __name__ == "__main__":
    main()



#NOTES
# Wall width
#1.98e5 - 1.154e5 = 82600hz walls
#Wall height = 55.1db's
#note that walls do NOT count towards signal we want to read, so they act as a hinderance. This is why we actually might need to check the full width
#   Fix for the walls is just do do a slightly less than 100,000hz jump when finding strong + wide enough signal
#First trial params:
# width: 5.7e4 - 4.459e4
# height: 47.9dbs
