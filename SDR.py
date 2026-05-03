import numpy as np
import json
from rtlsdr import RtlSdr
from scipy.signal import decimate, firwin, lfilter
import sounddevice as sd
from dejavu import Dejavu
from dejavu.logic.recognizer.file_recognizer import FileRecognizer
from scipy.io.wavfile import write
import time
import soundfile as sf
import tempfile
import os
import psycopg2
import threading
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import uvicorn

with open("dejavu.cnf.SAMPLE") as f:
    config = json.load(f)
djv = Dejavu(config)

app = FastAPI()

latest_scan = []
scan_lock = threading.Lock()


############################ Basic signal I/O: #############################


############################################################################
#
# Name:        calcSNR
# Description: Calculates the signal to noise ratio of a passed signal.
# Parameters:  ndarray singleStationIQSample - The IQ representation (time domain) of scanned signal
#              double frequencyDomSamples - In frequency domain, the samples of the entire scan, used to determine the noise floor power (not db)
# Return Value: double - The SNR (signal to noise) ratio
#
############################################################################
def calcSNR(singleStationIQSample, frequencyDomSamples): 
    signal_pow = np.mean(np.abs(singleStationIQSample) ** 2)
    noise_pow = np.percentile(np.abs(frequencyDomSamples)**2, 15) / len(frequencyDomSamples)
    return  10 * np.log10(signal_pow / noise_pow) 
 




############################################################################
#
# Name:        extractFromTargetCenter
# Description: Extracts a single FM signal from an existing scan in its IQ representation, via shifting the target to the center
# Parameters:  ndarray samples - The IQ representation (time domain) of scanned radio samples
#              RtlSdr sdr - The SDR object used for scanning (1 only)
#              relativeCenterFrequency - The location of the target we want to rotate to the center 
#              relative to the current center frequency  (as in the sdr's center frequency it used for the scan)
# Return Value: ndarray - The IQ representation of the FM signal (and only the signal)
#
############################################################################
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

############################################################################
#
# Name:        convertFrequencyDomSamplesToDB
# Description: Converts the frequency representation of radio sample data into decibels in frequency domain
# Parameters:  ndarray frequencyDom - The frequency domain representation of scanned radio samples
# Return Value: ndarray - The decibel representation of the samples
#
############################################################################
def convertFrequencyDomSamplesToDB(frequencyDom):
    powerFreqDom = np.abs(frequencyDom) ** 2
    return 10 * np.log10(powerFreqDom) # db representation


############################################################################
#
# Name:        chunkScan
# Description: Scans the desired duration of signals broken up into chunks based on the desired rate. 
#              Mainly created to circumvent usb buffer overflow issues (which occured on Linux but not Windows).
# Parameters:  RtlSdr sdr - The SDR object used for scanning (1 only)
#              recordingDuration - How many seconds of audio the samples will hold
#              int rate - How many samples get read per scan
# Return Value: ndarray - The data representation of radio samples collected over recordingDuration's value, in seconds
#
############################################################################
def chunkScan(sdr, recordingDuration, rate): 
    # Note that value must divide the samplerate * recordingduration (no float val)
    AmountToRun = (int)((sdr.sample_rate * recordingDuration) / rate) 
    chunks = [] 
    for i in range(0, AmountToRun):
        sample = sdr.read_samples(rate)
        chunks.append(sample) 
    return np.concatenate(chunks) 

########################## Fingerprinting methods ##########################

############################################################################
#
# Name:         runRecognize
# Description:  Converts the raw sample of 1 FM station to hashcode then checks for matches in database, returning results
# Parameters:   ndarray sample - The raw samples collected for the 1 FM station
# Return Value: [{}] - (list of dict) There is only 1 dictionary in the list, and it
#               contains attributes about time it took to query. Our main focus, the key "results" 
#               contain the attributes of the row the hashcode matched with
#
############################################################################
def runRecognize(sample):
    print(f"[DEBUG] Input sample length: {len(sample)} samples")
    print(f"[DEBUG] Input sample duration: {len(sample) / 2.56e6:.2f} seconds at 2.56MHz")
    phase_diff = np.angle(sample[1:] * np.conj(sample[:-1]))  #actually demodulates (data stored in frequency)
    # --- Downsample to audio rate ---
    audio = decimate(phase_diff, 6)        
    # Normalize
    audio /= np.max(np.abs(audio))          #scales between -1 and 1 (volume reasons)
    print(f"[DEBUG] Audio duration: {len(audio) / (2.56e6/6):.2f} seconds at ~426kHz")
    
        
    with tempfile.NamedTemporaryFile(suffix='.flac', delete=False) as tmp:
        sf.write(tmp.name, audio.astype(np.float32), 48000, format='FLAC')  
    temp_path = tmp.name
    print(f"[DEBUG] temp file created: {temp_path}")
    try:
        result = djv.recognize(FileRecognizer, temp_path)
        if result.get("results") and len(result["results"]) > 0:
            try:
                conn = psycopg2.connect(
                    host="rp-db-1",
                    database="dejavu",
                    user="postgres",
                    password="password"
                )
                cur = conn.cursor()

                for match in result["results"]:
                    song_id = match.get("song_id")
                    if song_id:
                        cur.execute(
                            "SELECT genre, year, artist FROM songs WHERE song_id = %s",
                            (song_id,)
                        )
                        db_result = cur.fetchone()
                        if db_result:
                            match["genre"] = db_result[0] or ""
                            match["year"] = db_result[1] or 0
                            match["artist"] = db_result[2] or ""
            
                cur.close()
                conn.close()

            except Exception as e:
                print(f"[WARNING] Could not connect to database: {e}")

        print(f"[DEBUG] recognize returned: {result}")
        return result
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.unlink(temp_path)

############################################################################
#
# Name:         recognizeAllSignals
# Description:  Fingerprints all signals that are passed to it and returns data collected
#               from fingerprinting
# Parameters:   [(double, ndarray)] sample: 
#                   double - The frequency location of the strong signal (in MHz)
#                   ndarray - The raw samples collected for a given signal
# Return Value: [{}] - (list of dict) Theres only 1 dict in the list. Each key:value pair 
#                      is an attribute about the signal recovered from the database
#
############################################################################
def recognizeAllSignals(signals):
    ans = []
    for i in range(0, len(signals)):
        filtered = signals[i][1]
        recognizeResult = runRecognize(filtered)
        if len(recognizeResult.get("results", [])) > 0:
            result = recognizeResult["results"][0]
            full_name = result.get("song_name", b"").decode("utf-8") if isinstance(result.get("song_name"), bytes) else result.get("song_name", "")
            # Split on " - " to separate title and artist
            if " - " in full_name:
                title, artist = full_name.split(" - ", 1)
            else:
                title, artist = full_name, ""
            filteredRecognizeResult = {
                "title": title,
                "artist": artist,
                "genre": result.get("genre", ""),
                "year": result.get("year", 0)
            }
        else:
            filteredRecognizeResult = {
                "title": "",
                "artist": "",
                "genre": "",
                "year": 0
            }
        filteredRecognizeResult["station"] = f"{signals[i][0]} FM"
        filteredRecognizeResult["strength"] = signals[i][2]
        print(filteredRecognizeResult)
        ans.append(filteredRecognizeResult)
    return ans

############################### FM detection ###############################


############################################################################
#
# Name:         convertRelativeFrequencyToActual
# Description:  Returns the actual frequency where a signal was located given how 
#               far away it is from the central frequency of a scan
# Parameters:   int centralFreq - The center frequency the scan was done at
#               int offset - The location relative to the center of the scan where the desired location for conversion is.
# Return Value: int - The actual frequency (in Hz) where the offset is
#
############################################################################

def convertRelativeFrequencyToActual(centralFreq, offset): # Given the location a desired frequency is on a sample ndArray, returns the actual frequency value that the signal is located at, as a sample is normally formatted in realativity to the central frequency
    return centralFreq + offset # targetFrequency should be relative, as the value is its distance from the central frequency, thats why this simple formula works


############################################################################
#
# Name:         getSignalAttributes
# Description:  Gets characteristics of a signal given its start location 
# Parameters:   int i - The start location of where a signal was detected
#               ndarray representationOfFrequencies - Array representation of radio scan in decibels (Frequency domain)
#               float thresholdForSignal - The signal strength we consider the start of a strong signal, also tells us when the signal ends
# Return Value: (int, int, int) - The location of the signal's center, the width, and the end.
#
############################################################################
#Returns the peak of a signal and its width
def getSignalAttributes(i, representationOfFrequencies, threshholdForSignal): # Given the starting loation of a signal, traverses the signal till it finds the peak. I will return the end of the signal, so we make sure to not count the same signal twice
    guardStart = 100 
    guard = guardStart
    startI = i
    max = -100 #Because I'm using personally using decibels, negative values are possible, so the starting value is -100 db 
    maxI = -1
    sampleLength = len(representationOfFrequencies)
    while True: 
        if i >= sampleLength or guard <= 0: 
            i-=1 #Sort of pointless, but If here, it means the i before it was the last frequency of signal
            break 
        currYVal = representationOfFrequencies[i]
        if currYVal < threshholdForSignal: 
            guard-=1
        else:
            guard = guardStart
        if currYVal > max: # Keeping track of where peak is
            max = currYVal 
            maxI = i 
        i+=1
    # maxI = center, i-startI = width, i+1000 = end (+1000 is just for a 'cooldown' in signal proximity)
    return (maxI, i - startI, i + 1000) 


############################################################################
#
# Name:         calcRelativeAcceptedStrength
# Description:  Using an estimate for the noise floor, determines what decibel strength 
#               is considered a strong signal (the starting strength of a strong signal, as in its minimum strength)
# Parameters:   ndarray db - The decibel representation of an entire scan's samples
# Return Value: Float, float - The signal strength we consider the start of a strong signal , The very roughly estimated noise floor
#
############################################################################
def calcRelativeAcceptedStrength(db):
    relativeThresholdVal = 18.5
    floorEstimateDb = np.average(np.percentile(db, 15)) 
    return floorEstimateDb + relativeThresholdVal

############################################################################
#
# Name:        removeDuplicateStations
# Description: Detects if signals are too close to each other and removes them if true
# Parameters:  [(double, ndarray)] ans: 
#               double - The frequency location of the strong signal (in MHz) 
#               ndarray - The raw samples collected for a given signal
# Return Value: [(double, ndarray)] : Only contains pairs of non-conflicting signals
#               double - The frequency location 
#               ndarray - The raw samples collected for a given signal
############################################################################
def removeDuplicateStations(ans): 
    i = 0
    while (i < len(ans) - 1):    
        if(ans[i + 1][0] - ans[i][0] < 0.35): 
            # root mean square is a way of comparing strength
            rmsI = np.sqrt(np.mean(np.abs(ans[i][1]) ** 2)) 
            rmsNext = np.sqrt(np.mean(np.abs(ans[i + 1][1]) ** 2))
            if( rmsI > rmsNext): 
                ans.pop(i + 1)
                i+=1
            else:
                ans.pop(i)
        else: 
            i+=1
    return ans



############################################################################
#
# Name:        findStrongSignals
# Description: Finds strong signals for a given array of a radio scan in decibels and returns
#              all the signals found in the scan, relative to the central frequency 
#              (as in -2 means 2hz left from the central frequency the scan occured at)
# Parameters:  ndarray representationOfFrequencies - Array representation of radio scan in decibels (Frequency domain)
#              float thresholdForSignal - The signal strength we consider the start of a strong signal 
#              int thresholdForWidth - The signal width (in Hz) we consider the size of an accepted signal
#              int sample_rate - The rate at which the SDR scanned for samples
# Return Value: float[] - (list of floats) The locations of strong signals relative to the central frequency
#
############################################################################
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


############################################################################
#
# Name:         findAllSignalsInFM
# Description:  Traverses the entire FM band with an RTLSDR and returns all strong
#               signals that were detected within and their associated audio.
# Parameters:   RtlSdr sdr - The SDR object used for scanning (1 only)
#               recordingDuration - How duration of the audio that is recorded
# Return Value: [(double, ndarray)]: 
#               double - The frequency location of the strong signal (in MHz)
#               ndarray - The raw samples collected for a given signal
#
############################################################################
def findAllSignalsInFM(sdr, recordingDuration):

    rawAns = []
    strongSignalWidth = 180_000 
    for i in range(1,10): 
        print("CURRENT CENTER FREQ:" + str(sdr.center_freq))
        # Scans in chunks to prevent usb buffer overflow 
        samples = chunkScan(sdr, recordingDuration, sdr.sample_rate/4) 
        frequencyDom = np.fft.fftshift(np.fft.fft(samples))   # turns samples from time domain to frequency domain (what we want). 
        db = convertFrequencyDomSamplesToDB(frequencyDom)
        # determines what signal strength (in db) is considered strong
        strongSignalThreshold = calcRelativeAcceptedStrength(db) 
        strongSignals = findStrongSignals(db, strongSignalThreshold, strongSignalWidth, sdr.sample_rate) 
        for signal in strongSignals: 
            frequencyLocation = round((convertRelativeFrequencyToActual(sdr.center_freq, signal))/1e6, 1)
            filtered = extractFromTargetCenter(samples, sdr, round(signal,6))
            print("Strong signal found at: " + str(frequencyLocation) )
            snr = calcSNR(filtered, frequencyDom) # Aquires the signal to noise ratio of given signal
            rawAns.append( (frequencyLocation, filtered, snr) ) 
        sdr.center_freq += sdr.sample_rate - 200_000 
    ans = removeDuplicateStations(rawAns)
    print("Accepted signal count: " + str(len(ans)))
    return ans

def updateSSEData(data):
    global latest_scan
    with scan_lock:
        latest_scan = list(data)

@app.get("/api/sse/stations")
def stream_stations():
    def event_stream():
        last_payload = None
        while True:
            with scan_lock:
                payload = json.dumps(latest_scan)

            if payload != last_payload:
                yield f"data: {payload}\n\n"
                last_payload = payload
            else:
                yield ": keep-alive\n\n"

            time.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
             
###########################################################################
def main():
    sdr = RtlSdr()  
    sdr.gain = 'auto'
    sdr.sample_rate = 2.56e6    
    runTime = 180
    while(True):     
        startTime = time.time()
        # exact starting point to guarantee the 8th scan will fully be in the FM band 
        sdr.center_freq = 89e6 
        allDetectedSignals = findAllSignalsInFM(sdr, 5)
        allFingerPrintedSignals = recognizeAllSignals(allDetectedSignals)

        updateSSEData(allFingerPrintedSignals)

        with open("/code/ddb_prototype/songs.json", "w") as file: 
            json.dump(allFingerPrintedSignals, file, indent=1)

        scanDuration = time.time() - startTime
        allDetectedSignals.clear()
        allFingerPrintedSignals.clear()
        time.sleep(max(0,(runTime - scanDuration)))
    # TODO:  When exit call recieved from frontend, close sdr object
    sdr.close() # do 3 minute

if __name__ == "__main__":
    threading.Thread(target=main, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=8000)







