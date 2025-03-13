import mido
from mido import MidiFile
import sounddevice as sd
import numpy as np
from scipy import signal
from scipy.signal import butter, lfilter
import soundfile as sf

def parse_midi(file_path):
    '''
    Parse MIDI file

    :param file_path:
    :return: list containing MIDI information (start_time, duration, pitch)
    '''
    mid = MidiFile(file_path)
    ticks_per_beat = mid.ticks_per_beat
    tempo = 500000

    events = []
    for track in mid.tracks:
        abs_time = 0
        for msg in track:
            abs_time += msg.time
            events.append((abs_time, msg))

    # sort the event by absolute time line
    events.sort(key=lambda x: x[0])

    current_time = 0.0
    current_tempo = tempo
    prev_abs_ticks = 0
    active_notes = {}
    notes = []

    for abs_ticks, msg in events:
        delta_ticks = abs_ticks - prev_abs_ticks
        prev_abs_ticks = abs_ticks
        delta_seconds = mido.tick2second(delta_ticks, ticks_per_beat, current_tempo)
        current_time += delta_seconds

        if msg.type == 'set_tempo':
            current_tempo = msg.tempo
        elif msg.type == 'note_on' and msg.velocity > 0:
            key = (msg.channel, msg.note)
            active_notes[key] = current_time
        elif msg.type in ['note_off', 'note_on'] and (msg.velocity == 0 or msg.type == 'note_off'):
            key = (msg.channel, msg.note)
            if key in active_notes:
                start = active_notes.pop(key)
                notes.append((start, current_time - start, msg.note))

    return sorted(notes, key=lambda x: x[0])


def generate_audio(notes, sample_rate=44100, noise_ratio=0.1,
                   adsr_params=(0.01, 0.1, 0.7, 0.1)):
    """
    Generate the mix wave including a symple ADSR and noise control

    param：
    - notes: (start_time, duration, pitch)
    - sample_rate: default 44100
    - noise_ratio:（0.0-1.0）
    - adsr_params: (attack_time, decay_time, sustain_level, release_time)

    return：
    audio list
    """
    if not notes:
        return np.zeros(0)

    max_time = max(start + dur for start, dur, _ in notes)
    audio = np.zeros(int(np.ceil(max_time * sample_rate)) + 1)

    attack_time, decay_time, sustain_level, release_time = adsr_params

    # mixed wave ratio, can modify it to simulate NES or other old game console
    wave_ratios = {
        'square': 0.75,
        'triangle': 0.3,
        'noise': noise_ratio
    }




    def lowpass_filter(data, cutoff=2000, order=4):
        nyq = 0.5 * sample_rate
        normal_cutoff = cutoff / nyq
        b, a = butter(order, normal_cutoff, btype='low')
        return lfilter(b, a, data)

    for start, dur, pitch in notes:
        freq = 440 * 2 ** ((pitch - 69) / 12)
        start_sample = int(start * sample_rate)
        end_sample = int((start + dur) * sample_rate)
        total_samples = end_sample - start_sample
        if total_samples <= 0:
            continue
        t = np.linspace(0, dur, total_samples, False)
        square = 0.6 * signal.square(2 * np.pi * freq * t, duty=0.5) #generate square wave
        triangle = 0.6 * signal.sawtooth(2 * np.pi * freq * t, 0.5) #generate triangle wave
        noise = np.random.normal(0, 0.3, total_samples)
        noise = lowpass_filter(noise, cutoff=3000) * 0.5

        # Control the ratio of different wave.

        mixed = (
                square * wave_ratios['square'] +
                triangle * wave_ratios['triangle'] +
                noise * wave_ratios['noise']
        )




        envelope = np.ones(total_samples)
        attack_samples = min(int(attack_time * sample_rate), total_samples)
        remaining = total_samples - attack_samples
        decay_samples = min(int(decay_time * sample_rate), remaining)
        remaining -= decay_samples
        release_samples = min(int(release_time * sample_rate), total_samples)
        sustain_samples = max(0, total_samples - attack_samples - decay_samples - release_samples)
        if attack_samples > 0:
            envelope[:attack_samples] = np.linspace(0, 1, attack_samples)
        if decay_samples > 0:
            decay_start = attack_samples
            decay_end = decay_start + decay_samples
            envelope[decay_start:decay_end] = np.linspace(1, sustain_level, decay_samples)
        if sustain_samples > 0:
            sustain_start = attack_samples + decay_samples
            envelope[sustain_start:-release_samples] = sustain_level
        if release_samples > 0:
            release_start = max(0, total_samples - release_samples)
            env_slice = envelope[release_start:]
            env_slice *= np.linspace(1, 0, release_samples)
        mixed *= envelope
        buffer_end = start_sample + total_samples
        if buffer_end > len(audio):
            mixed = mixed[:len(audio) - start_sample]
            buffer_end = len(audio)
        audio[start_sample:buffer_end] += mixed
    #     Lower the peak noise
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio /= peak * 1.4

    return audio


def save_audio(audio, sample_rate=44100, file_path="output.wav"):
    sf.write(file_path, audio, sample_rate)
    
    

if __name__ == '__main__':
    midi_file = 'dataset/Lemon-Tree.mid'  # 替换为你的MIDI文件路径
    notes = parse_midi(midi_file)
    audio = generate_audio(notes)

    
    # sd.play(audio, 44100)
    # sd.wait()
    
    save_audio(audio, file_path="output.wav")
    