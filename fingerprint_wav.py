import sys
import os
from dejavu import Dejavu

# Usage: python fingerprint_wav.py /path/to/music

if len(sys.argv) < 2:
    print("Usage: python fingerprint_wav.py <dir>")
    sys.exit(1)

MUSIC_DIR = sys.argv[1]

config = {
    "database_type": "postgres",
    "database": {
        "host": "db",
        "user": "postgres",
        "password": "password",
        "database": "dejavu"
     }
 }

def get_wav(directory):
    wav_files = []
    for root, _, files in os.walk(directory):
        for f in files:
            if f.lower().endswith(".wav"):
                wav_files.append(os.path.join(root,f))
    return wav_files

def fingerprint_files(djv, files):
    for file in files:
        try:
            print(f"Fingerprinting: {file}")
            djv.fingerprint_file(file)
        except Exception as e:
            print(f"Failed: {file} -> {e}")

def main():
    if not os.path.exists(MUSIC_DIR):
        print ("Directory doesn't exist", MUSIC_DIR)
        sys.exit(1)

    wav_files = get_wav(MUSIC_DIR)

    if not wav_files:
        print("No .wav files found")
        return

    print(f"Found {len(wav_files)} wav files")

    djv = Dejavu(config)

    fingerprint_files(djv, wav_files)

    print("Done fingerprinting")

if __name__ == "__main__":
    main()