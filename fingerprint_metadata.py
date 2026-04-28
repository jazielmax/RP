import sys
import os
from dejavu import Dejavu
from mutagen.flac import FLAC

if len(sys.argv) < 2:
    print("Usage: python fingerprint.py <dir>")
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

def get_audio_files(directory):
    files = []
    for root, _, filenames in os.walk(directory):
        for f in filenames:
            if f.lower().endswith(".flac"):
                files.append(os.path.join(root, f))
    return files

def extract_metadata(file_path):
    try:
        audio = FLAC(file_path)

        artist = audio.get("artist", [None])[0]
        genre = audio.get("genre", [None])[0]

        date = audio.get("date", [None])[0]
        year = int(date[:4]) if date else None

        return artist, genre, year

    except Exception as e:
        print(f"Metadata error: {file_path} -> {e}")
        return None, None, None

def get_last_song_id(djv):
    with djv.db.cursor() as cur:
        cur.execute("""
            SELECT song_id
            FROM songs
            ORDER BY song_id DESC
            LIMIT 1;
        """)
        return cur.fetchone()[0]

def fingerprint_files(djv, files):
    for file in files:
        try:
            print(f"Fingerprinting: {file}")

            # Step 1: fingerprint (inserts song)
            djv.fingerprint_file(file)

            # Step 2: get inserted song_id
            song_id = get_last_song_id(djv)

            # Step 3: extract metadata
            artist, genre, year = extract_metadata(file)

            # Step 4: update DB
            djv.db.update_song_metadata(
                song_id,
                artist=artist,
                genre=genre,
                year=year
            )

            print(f"Updated metadata for song_id={song_id}")

        except Exception as e:
            print(f"Failed: {file} -> {e}")

def main():
    if not os.path.exists(MUSIC_DIR):
        print("Directory doesn't exist", MUSIC_DIR)
        sys.exit(1)

    audio_files = get_audio_files(MUSIC_DIR)

    if not audio_files:
        print("No .flac files found")
        return

    print(f"Found {len(audio_files)} FLAC files")

    djv = Dejavu(config)

    fingerprint_files(djv, audio_files)

    print("Done fingerprinting")

if __name__ == "__main__":
    main()