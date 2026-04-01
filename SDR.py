import numpy as np
import scipy.io.wavfile
from rtlsdr import RtlSdr
from scipy.signal import decimate, firwin, lfilter
#from scipy.io.wavfile import write 
import matplotlib.pyplot as plt # used for pysdr example code
import sounddevice as sd
#TODO: centerI being returned from strong signal is literal outside of the possible scan range

#NOTE: Signal detection should be done one chunk at a time, NOT: scan all, then process
# NOTE: Power peaks may not denote a strong signal, as they can be short lived, it is also necessary to measure the width of the signal, as it should be close to the bandwidth of FM radio (200,000hz)



#JSON with key frequency, store wav file straight in this

fileCount = 0
######################## Signal finding functions: ########################
def convertRelativeFrequencyToActual(centralFreq, offset): # Given the location a desired frequency is on a sample ndArray, returns the actual frequency value that the signal is located at, as a sample is normally formatted in realativity to the central frequency
    return centralFreq + offset # targetFrequency should be relative, as the value is its distance from the central frequency, thats why this simple formula works

#Returns the peak of a signal and its width
def getSignalAttributes(i, representationOfFrequencies, threshholdForSignal): # Given the starting loation of a signal, traverses the signal till it finds the peak. I will return the end of the signal, so we make sure to not count the same signal twice
    #impliment guard system, as dips may occur even on strong signals, wewe need a guard of some sort (maybe around 10-15ish)
    guardStart = 80 # NOTE: We need to play around with this value
    guard = guardStart
    startI = i
    max = -100 #Because I'm using personally using decibels, negative values are possible, so the starting value is -100 db 
    maxI = -1
    sampleLength = len(representationOfFrequencies)
    while True: #Just a goofy do while-like to allow repOfFreq to be a var (condenses code)
        currYVal = representationOfFrequencies[i]
        if currYVal < threshholdForSignal: 
            guard-=1
        else:
            guard = guardStart
        if i >= sampleLength or guard <= 0: 
            i-=1 #Sort of pointless, but If here, it means the i before it was the last frequency of signal
            break #case to end while
        if currYVal > max: # Keeping track of where peak is
            max = currYVal # Strength of peak
            maxI = i # the location of the highest recorded peak
        i+=1
    #NOTE: The maxI value that is returned is stored as a relative frequency, as it it states how far away it is from the central frequency. This must be converted (though the convertRelativeFrequencyToActual) in order for it to be useful
    return (maxI, i - startI, i + 1000) # maxI = center, i-startI = width, i = end. DECIDE WHETHER OR NOT TO KEEP + 1000

def findStrongSignals(representationOfFrequencies: np.ndarray, threshholdForSignal, thresholdForWidth, sample_rate): # Given a frequency domain sample already set for power, returns the frequencies where the center of strong signals are
    ans = [] # will hold a list frequencies
    sampleLength = len(representationOfFrequencies)
    centerI = -1
    width = -1
    i = 0
    while i < sampleLength: 
        if(representationOfFrequencies[i] >= threshholdForSignal):
            centerI, width, i = getSignalAttributes(i, representationOfFrequencies, threshholdForSignal) # i gets set to the end of the signal
            if width >= thresholdForWidth:
                offset = (centerI - sampleLength/2) * (sample_rate / sampleLength) # Essentially an inverses the FFT + FFTshift
                #ans.append(convertRelativeFrequencyToActual(centralFreq, centerI)) # consider some form of floor or ceiling? Most signals are like 101.1e6, so we only need
                ans.append(offset) # TESTING VERSION FOR SEEING IF IT WORKS
        else:
            i+=1
    return ans
#NOTE Maybe after finding strong signal we skip around 5,000hz? Guarantees to not include high interference signal
######################## Basic signal I/O: ################################

#This just behaves a parameterized variant of the sdr constructor
def createSdrObj (sample_rate, center_freq, gain):
    sdr = RtlSdr()
    sdr.sample_rate = sample_rate
    sdr.center_freq = center_freq # The center point of what will be recorded, in hz
    sdr.gain = gain
    return sdr

#NOTE: WE NEED TO IMPLIMENT OF BAND PASS FILTER, NOT the current low-pass filter

def extractFromTargetCenter(samples, sdr, relativeCenterFreq):
    # 1. SHIFT THE SAMPLES: Drag the target signal down to 0 Hz
    n = np.arange(len(samples))
    shifted_samples = samples * np.exp(-1j * 2 * np.pi * relativeCenterFreq / sdr.sample_rate * n) # shifts the desired signal down to the central frequency location
    nyq = sdr.sample_rate / 2 
    cutoff = 100e3 # NOTE: firwin cutoff is from 0 to the edge, so you do bandwidth / 2. For 200kHz bandwidth, we want 100kHz cutoff.
    tapCount = 101 
    taps = firwin(tapCount, cutoff / nyq) 
    filtered = lfilter(taps, 1.0, shifted_samples) # filters the signal at 0 (which is the target now)
    return decimate(filtered, 10) # Decimate protects the signal at the central frequency, which is why we had to shift our target to the center


def lowPassExtract(samples, sdr): # Retrieves the signal at central frequency
    nyq = sdr.sample_rate / 2 # nyquist frequency
    cutoff = 200e3 # cutoff is related to bandwidth
    tapSize = 101 # larger = more computation, but more accurate
    taps = firwin(tapSize, cutoff / nyq) # Creates the filter (FIR). Cut off is the width of the signal, we normalize by diving by the nyquist  
    return decimate( lfilter(taps, 1.0, samples), 10 ) #Uses the filter to cut out the target signal from the sample array

def recordAudio(target, fileName):
    phase_diff = np.angle(target[1:] * np.conj(target[:-1]))  #actually demodulates (data stored in frequency)
    # --- Downsample to audio rate ---
    audio = decimate(phase_diff, 6)        # 256 kHz → 48 kHz        (48khz )
    # Normalize
    audio /= np.max(np.abs(audio))          #scales between -1 and 1 (volume reasons)
    print("Recording audio...")

    #TODO: Store np.array into JSON file, key is frequency of center (possibly store full result in array first for analysis)
    #scipy.io.wavfile.write(fileName, 42660, audio) Actual application code MAIN DO THIS COMMENT BELOW OUT
    sd.play(audio, 42660)
    sd.wait() 




def convertIQSamplesToDB(samples):
    frequencyDom = np.fft.fftshift(np.fft.fft(samples))   # turns samples from time domain to frequency domain (what we want). 
    powerFreqDom = np.abs(frequencyDom) ** 2
    return 10 * np.log10(powerFreqDom) # db representation

def calcRelativeStrength(db):
    relativeThresholdVal = 23.5112594148 # distance from the floor that we consider a strong signal
    floorEstimate = np.average(np.percentile(db, 15)) # noise estimate, its the bottom 15% of signal strengths
    return floorEstimate + relativeThresholdVal

def findAllSignalsInFM(sdr, recordingDuration):
    strongSignalWidth = 85_000 # The width signal must be do be considered strong 
    for i in range(1,9): # we scan 8 times (1-8)
        samples = sdr.read_samples(sdr.sample_rate * recordingDuration) 
        db = convertIQSamplesToDB(samples)
        strongSignalThreshold = calcRelativeStrength(db) # defines what signal strength (in db) is considered strong
        strongSignals = findStrongSignals(db, strongSignalThreshold, strongSignalWidth, sdr.sample_rate) # finds strong signals within sample
        for signal in strongSignals: # Plays all signals
            frequencyLocation = convertRelativeFrequencyToActual(sdr.center_freq, signal)
            print("Strong signal found at: " + (f"{frequencyLocation:.2e}"))
            filtered = extractFromTargetCenter(samples, sdr, signal)
            recordAudio(filtered, "test.wav") # TODO: WILL STORE RESULT IN ARRAY FORM
            sdr.center_freq += sdr.sample_rate #Traverses the next sample
            print("CURRENT CENTER FREQ:" + str(sdr.center_freq))

#NOTE: MIGHT WANT TO RETURN LOWPASS/BANDPASS AS IT'S DECIMATED FORM, though we do need the raw form for RMS
# Note that filtering retains the size of the array, decimate will actually shrink the array
###########################################################################
def main():

    strongSignals = []
    #Reading
    #time = 5
    sample_rate = 2.56e6      # sample per second
    center_freq = 87.8125e6 # exact starting point to guaratee the 8th scan will fully be in the FM band (not partially outside)
    #center_freq = 101.7e6   # Strong signal  radio tuning i * 0.2e3
    #center_freq = 104.10e6  # VERY GOOD SIGNAL FOR WEAKEST STRONG SIGNALS
    #center_freq = 102.1e6
    #center_freq = 99.9e6
    #center_freq = 94.7e6 Signal that is too weak/we dont want this to be counted!
    gain = 'auto'
    sdr = createSdrObj(sample_rate, center_freq, gain)          # create SDR object

    print("Receiving samples...")
    #samples = sdr.read_samples(sdr.sample_rate * time )  #2.4e6 samples read / 2.4e6 samples rate = 1 second

    # --- FM Demodulation ---
    print("Demodulating FM...")
    #filtered = lowPassExtract(samples, sdr) # note that filtered is effectively the signal at central frequency (when don e with low-pass filter)
    #filtered = extractFromTargetCenter(samples, sdr, 0)

    # signal detection code 
    """ frequencyDom = np.fft.fftshift(np.fft.fft(samples))   # turns samples from time domain to frequency domain (what we want). 
    powerFreqDom = np.abs(frequencyDom) ** 2
    db = 10 * np.log10(powerFreqDom) # adding a very small amount ensures we do not do log10(0) which in matplotlib shows an empty/null value
    #We have to do a shift any time we do FFT (fast fourier transfer) as it outputs from Greatest to least, but we want lowest to heighest frequencies with 0 in the middle. This makes the center frequency located at 0 and allows us to determinine at what hz the frequencies are in relation to the central frequency    
 """
   


    # Finding all strong signals
    """ 
     relativeThresholdVal = 23.5112594148 # distance from the floor that we consider a strong signal
    floorEstimate = np.average(np.percentile(db, 15)) # noise estimate
    strongSignalThreshold = floorEstimate + relativeThresholdVal
    strongSignals = findStrongSignals(sdr.center_freq, db, strongSignalThreshold, strongSignalWidth, sdr.sample_rate)
    for signal in strongSignals: # Plays all signals
        frequencyLocation = convertRelativeFrequencyToActual(sdr.center_freq, signal[1])
        print("Strong signal found at: " + (f"{frequencyLocation:.2e}"))
        filtered = extractFromTargetCenter(samples, sdr, signal[1])
        #global fileCount
        recordAudio(filtered, "test.wav")
        #fileCount+=1 
    """
    findAllSignalsInFM(sdr, 5)
        

    # tests on signal at central frequency
    """ filtered = lowPassExtract(samples, sdr)
    rms =  np.sqrt(np.mean(np.abs(filtered) ** 2))
    rms_inDb = 20 * np.log10(rms)
    print ("Guess of noise floor: " + str(floorEstimate) + "\nProposed threshold: " + str(strongSignalThreshold) + "\nRMS value:" + str(rms_inDb)) """
    # Relative RMS value for a clear signal:
    #rms =  np.sqrt(np.mean(np.abs(filtered) ** 2))# Root mean square is used to find how much noise is in a signal. IMPORANT: RMS MUST BE CALCULATED FROM TIME DOMAIN
    #rms_inDb = 20 * np.log10(rms) 
    #print ("Guess of noise floor: " + str(floorEstimate) + "\nProposed threshold: " + str(strongSignalThreshold) + "\nRMS value:" + str(rms_inDb))

    sdr.close()
    ######### CODE TAKEN FROM PYSDR.org#######################
    
    #Fs = 1 # Hz   
    #S_mag = db# gives us power for the y axis
    #f = f = np.linspace( sdr.sample_rate / -2, sdr.sample_rate / 2, num=db.size)
    #plt.plot(f, S_mag,'.-')
    #plt.show() 
     
    ##########################################################
    #look into rtl_power (sweeps data over wide frequency spectrum)

if __name__ == "__main__":
    main()


    #Current plan for strong signal detection:
    # 1. Estimate noise floor value
    # 2. Calculate relative threshold to deem a possible signal
    # 3(optional). LOOK INTO Run the scipy correlate function on a possible signal with a hardcoded strong signal, and accept the signal as strong for a constant confidence value (maybe like 0.4-0.6 confidence). Use frequency
    # possibly use mode = 'fft'
    #4: Once you have a list of prospective signals, use a RMS on each with a RMS (root mean square) threshold (must be relative to floor!) to guarantee all signals have no static noise
    #relativity testing:
    # width: -6.9e4 6.972e4 = 138,720, with threshold of 48 maybe we use a width of 100,000? set the cap to 200,000 to avoid interference
    # Now we need to calculate relativity! This was done with an estimated floor of 24.488740585217858 dbs
    # Noise at 23, desired signal at 43 low - 60 peak (do note I've found signals also at 43 but peak at 55, and they are not strong signals/should not be considered)
    # proposed threshold:  23.5112594148 + the noise (note that I use PLUS not multiply as you should not use multiplication or divison with db's, so the relativity is just the threshold - floor)
    # proposed width: 100,000


    #Removing cases with signal noise (note we have to do this for EACH candidate):
    #Steps: 
    #1. Using location of signal, use filtering to extract the signal from the IQ version (samples np.ndarray) 
    #2. Calculate RMS of the signal (just do root(mean(square()))), then convert to decibels with 20 * log10(RMSval).if its lower than the RELATIVE rms threshold, then we discard it
    #centerIdxInSample = len(db) // 2
    #Noisy rms: -33.22287864097743 at floor of 24.746768491034196
    #Clear rms case: - -28.8296887404954 at noise floor of 32.22499718260055

    #NOTE fftshift makes the central frequency located at n/2 (size of samples / 2)
    #NOTE taps - 1 / 2 will adjust a lfilter to for 0 to be central frequency
