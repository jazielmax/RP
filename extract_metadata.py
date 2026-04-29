from mutagen.flac import FLAC

audio = FLAC("/code/music/Billie Jean - Michael Jackson.flac")

for key, value in audio.tags.items():
    print(key, value)