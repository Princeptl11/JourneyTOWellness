import wave, struct, random, os, math

os.makedirs('static/audio', exist_ok=True)

def make_noise(filename, volume=8000, length=2):
    with wave.open(filename, 'w') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(44100)
        nframes = 44100 * length
        for _ in range(nframes):
            data = struct.pack('<h', random.randint(-volume, volume))
            f.writeframesraw(data)

def make_tone(filename, freq=440.0, length=2):
    with wave.open(filename, 'w') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(44100)
        nframes = 44100 * length
        for i in range(nframes):
            # simple sine wave with a little decay to sound slightly like a hit
            val = int(math.sin(2 * math.pi * freq * (i / 44100.0)) * 8000 * math.exp(-i/(44100.0*length/2)))
            data = struct.pack('<h', val)
            f.writeframesraw(data)

make_noise('static/audio/rain.wav', 4000, 3) # Sounds like rain/waterfall
make_noise('static/audio/ocean.wav', 2000, 3) # Softer noise
make_noise('static/audio/birds.wav', 1000, 3) # Very faint background noise placeholder
make_tone('static/audio/piano.wav', 261.63, 3) # Middle C
make_noise('static/audio/whitenoise.wav', 10000, 3) # Harsh white noise
print("Audio files created.")
