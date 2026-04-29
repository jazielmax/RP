import json
from dejavu import Dejavu
from dejavu.logic.recognizer.file_recognizer import FileRecognizer
import time

with open("dejavu.cnf.SAMPLE") as f:
    config = json.load(f)

# Create the Dejavu instance
djv = Dejavu(config)

def recognizeAllSignals():
    ans = []
    audio_file = "Do I Wanna Know - Arctic Monkeys.flac"
    
    try:
        print(f"Starting recognition of {audio_file}...")
        print("This may take 30-60 seconds for 1,000 songs...")
        
        start_time = time.time()
        recognizeResult = djv.recognize(FileRecognizer, audio_file)
        elapsed = time.time() - start_time
        
        print(f"Recognition completed in {elapsed:.2f} seconds")
        
        if recognizeResult and len(recognizeResult.get("results", [])) > 0:
            result = recognizeResult["results"][0]
            result["station"] = "LOCAL_FILE"
            print(f" Match found: {result.get('song_name')} by {result.get('artist_name')}")
        else:
            result = {
                "title": "Unknown",
                "artist": "Unknown", 
                "genre": "Unknown",
                "year": 0,
                "station": "LOCAL_FILE"
            }
            print("✗ No match found")
        
        ans.append(result)
        
    except KeyboardInterrupt:
        print("\nRecognition interrupted by user")
        raise
    except Exception as e:
        print(f"Error: {e}")
        ans.append({
            "title": "Error",
            "artist": "Error",
            "genre": "Error",
            "year": 0,
            "station": "ERROR"
        })
    
    return ans

def main():
    allFingerPrintedSignals = recognizeAllSignals()
    
    # Save to JSON
    with open("/code/ddb_prototype/songs.json", "w") as file:
        json.dump(allFingerPrintedSignals, file, indent=1)
    
    print(f"Saved results to /code/ddb_prototype/songs.json")

if __name__ == "__main__":
    main()