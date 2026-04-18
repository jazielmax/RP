import os
import sys
import subprocess

def download_playlist(url: str, dir: str):
    # create folder if doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format", "wav",
        "-f", "bestaudio/best",
        "-o", f"{dir}/%(playlist_index)s - %(title)s.%(ext)s",
        url
    ]

    print("Running:", " ".join(cmd))

    result = subprocess.run(cmd, check=False)

    if result.returncode != 0:
        print ("Download finished with errors")
    else:
        print("Download completed succesfully")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python wav_playlist.py <playlist_url> <dir>")
        sys.exit(1)

    playlist_url = sys.argv[1]
    output_dir = sys.argv[2]

    download_playlist(playlist_url, output_dir)
