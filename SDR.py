import numpy as np
import json
#import scipy.io.wavfile as wav
from rtlsdr import RtlSdr
from scipy.signal import decimate, firwin, lfilter
import sounddevice as sd
from dejavu import Dejavu
from dejavu.logic.recognizer.file_recognizer import FileRecognizer
from scipy.io.wavfile import write
import time
#TODO: centerI being returned from strong signal is literal outside of the possible scan range

#NOTE: Signal detection should be done one chunk at a time, NOT: scan all, then process
# NOTE: Power peaks may not denote a strong signal, as they can be short lived, it is also necessary to measure the width of the signal, as it should be close to the bandwidth of FM radio (200,000hz)
with open("dejavu.cnf.SAMPLE") as f:
    config = json.load(f)
djv = Dejavu(config)

def recognizeAsWav(audio, filename="temp.wav"):
    write(filename, 42660, audio.astype(np.float32))
    return djv.recognize(FileRecognizer, filename) 


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



#MOST LIKELY LINUX ERROR CASE
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

def runRecognize(target):
    phase_diff = np.angle(target[1:] * np.conj(target[:-1]))  #actually demodulates (data stored in frequency)
    # --- Downsample to audio rate ---
    audio = decimate(phase_diff, 6)        # 256 kHz → 48 kHz        (48khz )
    # Normalize
    audio /= np.max(np.abs(audio))          #scales between -1 and 1 (volume reasons)
    
    #sd.play(audio, 42660)
    #sd.wait()
    return recognizeAsWav(audio)  

    #TODO: Store np.array into JSON file, key is frequency of center (possibly store full result in array first for analysis)

    #scipy.io.wavfile.write(fileName, 42660, audio) Actual application code MAIN DO THIS COMMENT BELOW OUT
   
def convertIQSamplesToDB(samples):
    frequencyDom = np.fft.fftshift(np.fft.fft(samples))   # turns samples from time domain to frequency domain (what we want). 
    powerFreqDom = np.abs(frequencyDom) ** 2
    return 10 * np.log10(powerFreqDom) # db representation

def calcRelativeStrength(db):
    #relativeThresholdVal = 23.5112594148 # distance from the floor that we consider a strong signal
    relativeThresholdVal = 25 #Pretty good! Guaranteed a strong signal, set with width of 100,000 and found 
    floorEstimate = np.average(np.percentile(db, 15)) # noise estimate, its the bottom 15% of signal strengths
    return floorEstimate + relativeThresholdVal

def removeDuplicateStations(ans): #Center freq means no other centers should be at least 100,000 hz (or 0.1e6) or closer
#note that the ans array should be pre-sorted from list to greatest, in Mhz for the center frequency
    i = 0
    while (i < len(ans) - 1):     # ans is an array of pairs, [#][0] references frequency, [#][1] references the array representation of the .wav audio
        if(ans[i + 1][0] - ans[i][0] < 0.45): #If two signals are close enough in their central frequency, we infer they are duplicates (this is a rather cutthroat threshold, but our goal is 0 duplicates)
            rmsI = np.sqrt(np.mean(ans[i][1] ** 2)) # root mean square is a way of comparing strength
            rmsNext = np.sqrt(np.mean(ans[i + 1][1] ** 2))
            if( rmsI > rmsNext): # Strongest signal is chosen (more likely to be the real signal, not a reflection of it)
                ans.pop(i + 1)
            else:
                ans.pop(i)
        else: # We dont +=1 just in case when popping, another weak signal is found
            i+=1
    return ans

def chunkScan(sdr, recordingDuration, rate): # TEST ONE, DELETE
    AmountToRun = (int)((sdr.sample_rate * recordingDuration) / rate) # Note that the user should enter a value that divides the samplerate * recordingduration value (no float val)
    chunks = [] # chunks is a list 
    for i in range(0, AmountToRun):
        sample = sdr.read_samples(rate)
        #chunks.append(sdr.read_samples(rate)) # Reads a very small amount at a time
        chunks.append(sample) 

    return np.concatenate(chunks) # concatenates array into a ndarray, by default axis = 0, which means the 1st layer (The lists)

#Need to do a while based chunk scan, much smaller size, like 4000 bytes, but something that adds up to my desired sample rate (5 * 2.56e6)


def findAllSignalsInFM(sdr, recordingDuration):
    ans = {}
    rawAns = []
    #strongSignalWidth = 109_000 # The width signal must be do be considered strong 
    strongSignalWidth = 150_000 # The width signal must be do be considered strong 
    for i in range(1,10): # we scan 8 times (1-8)
        print("CURRENT CENTER FREQ:" + str(sdr.center_freq))
        samples = chunkScan(sdr, recordingDuration, sdr.sample_rate/4) # implements behavior of scanning signal, but in chunks for preventing buffer overflow 
        #samples = sdr.read_samples(sdr.sample_rate * recordingDuration)
        db = convertIQSamplesToDB(samples)
        strongSignalThreshold = calcRelativeStrength(db) # defines what signal strength (in db) is considered strong
        strongSignals = findStrongSignals(db, strongSignalThreshold, strongSignalWidth, sdr.sample_rate) # finds strong signals within sample
        for signal in strongSignals: # Plays all signals
            #signal = round(signal, -5) # Stations are placed up to the tenths place of Mhz (like 101.1), so this makes sure we actually get the true center
            frequencyLocation = round ((convertRelativeFrequencyToActual(sdr.center_freq, signal))/1e6, 1)
            filtered = extractFromTargetCenter(samples, sdr, round(signal, -5))

            recognizeResult = runRecognize(filtered) # TODO: WILL STORE RESULT IN ARRAY FORM
            if(len(recognizeResult["results"]) > 0):
                filteredRecognizeResult = recognizeResult["results"][0] # Takes out all the useless info we aren't using (runtime, query time, etc..). This assumes that results will have ONE dict that contains all the key:value pairs for attributes (but idk yet how its supposed to be)
            else:
                filteredRecognizeResult = dict()
            filteredRecognizeResult["station"] = (str(frequencyLocation) + " FM")
            print(filteredRecognizeResult)


            print("Strong signal found at: " + str(frequencyLocation) )
            #ans[round( (round(frequencyLocation, 5) / 1e6), 1) ] = rawAudioArr #returns the frequency in MHz (so 101 = 101e6)
            #rawAns.append( (round(frequencyLocation / 1e6) , rawAudioArr) )
            rawAns.append( (frequencyLocation, filteredRecognizeResult) ) # PLACEHOLDER VALUE
        sdr.center_freq += sdr.sample_rate - 200_000 #Traverses the next sample, with 200,000 hz of overlap to prevent ALL edge clipping
    
    _, ans = zip(*rawAns) # ans is just rawAns but with any possible duplicates filtered out. * is useda s the unpacking operator, _ is wildcard (as in disregard it). This is VERY ocaml coded
    ans = list(ans) # formats to a list of dict's that follows the desired format for out frontend
    print("Accepted signal count: " + str(len(ans)))
    return ans
             
###########################################################################
def main():
    sdr = RtlSdr()  # create SDR object
    sdr.gain = 'auto'
    sdr.sample_rate = 2.56e6      # sample per second
    runTime = 180
    while(True):     
        startTime = time.time()
        sdr.center_freq = 89e6 # exact starting point to guarantee the 8th scan will fully be in the FM band (not partially outside)
        # Finding all strong signals
        allDetectedSignals = findAllSignalsInFM(sdr, 5)

        #hashcodeSignals(allDetectedSignals) # will automatically update database with the detected songs
        with open("songs.json", "w") as file: # This just automates file closing
            json.dump(allDetectedSignals, file, indent = 1) #Writes dict to json 

        
            
        """     
        allDetectedSignals = dict(zip(allDetectedSignals.keys(), map(lambda x: x.tolist(), allDetectedSignals.values() ))) # Currentl only allows frequency keys, nparray values (due to .toList())
        
        #hashcodeSignals(allDetectedSignals) # will automatically update database with the detected songs
        with open("songs.json", "w") as file: # This just automates file closing
            json.dump(allDetectedSignals, file, indent = 2) #Writes dict to json 
            
        """
        scanDuration = time.time() - startTime
        time.sleep(max(0,(runTime - scanDuration)))
    sdr.close() # do 3 minute

if __name__ == "__main__":
    main()






