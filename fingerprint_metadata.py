import sys
import os
import json
from dejavu import Dejavu
from mutagen.flac import FLAC
from mutagen.easyid3 import EasyID3

if len(sys.argv) < 2:
    print("Usage: python fingerprint_metadata.py <dir>")
    sys.exit(1)

MUSIC_DIR = sys.argv[1]

with open("dejavu.cnf.SAMPLE") as f:
    config = json.load(f)
print(f"Using fingerprint_limit: {config.get('fingerprint_limit')}")

def get_audio_files(directory):
    files = []
    for root, _, filenames in os.walk(directory):
        for f in filenames:
            if f.lower().endswith((".flac", ".mp3")):
                files.append(os.path.join(root, f))
    return files

def extract_metadata(file_path):
    try:
        if file_path.lower().endswith(".flac"):
            audio = FLAC(file_path)
            artist = audio.get("artist", [None])[0]
            genre = audio.get("genre", [None])[0]
            date = audio.get("date", [None])[0]
        elif file_path.lower().endswith(".mp3"):
            audio = EasyID3(file_path)
            artist = audio.get("artist", [None])[0]
            genre = audio.get("genre", [None])[0]
            date = audio.get("date", [None])[0]
        else:
            return None, None, None
        
        year = None
        if date:
            try:
                year = int(date[:4])
            except:
                pass
        return artist, genre, year
        
    except Exception as e:
        print(f"Metadata error: {file_path} -> {e}")
        return None, None, None

def fingerprint_files(djv, files):
    for file in files:
        try:
            print(f"Fingerprinting: {file}")
            
            song_id = djv.fingerprint_file(file)
            
            if song_id:
                artist, genre, year = extract_metadata(file)
                djv.db.update_song_metadata(song_id, artist=artist, genre=genre, year=year)
                print(f"Updated metadata for song_id={song_id}: {artist}, {genre}, {year}")
            else:
                print(f"Warning: Could not get song_id for {file}")
                
        except Exception as e:
            print(f"Failed: {file} -> {e}")

def main():
    if not os.path.exists(MUSIC_DIR):
        print("Directory doesn't exist", MUSIC_DIR)
        sys.exit(1)

    audio_files = get_audio_files(MUSIC_DIR)
    
    if not audio_files:
        print("No audio files found (.flac, .mp3)")
        return
    
    print(f"Found {len(audio_files)} audio files")
    
    djv = Dejavu(config)
    print(f"Fingerprint limit is set to: {djv.limit}")
    fingerprint_files(djv, audio_files)
    
    print("Done fingerprinting")

if __name__ == "__main__":
    main()