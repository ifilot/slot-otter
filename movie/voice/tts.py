"""Synthesise narration lines with Kokoro-82M (local, Apache-2.0).

Runs in the separate TTS environment (movie/.venv-tts, Python 3.12):

    .venv-tts/bin/python voice/tts.py jobs.json out_dir

jobs.json: [{"id": "s03_edge.2", "text": "...", "voice": "af_heart", "speed": 0.94}, ...]
Writes <out_dir>/<hash>.wav (24 kHz mono) per line, cached by (text, voice,
speed), and <out_dir>/manifest.json with duration and phonemes per id.
"""
import hashlib
import json
import os
import sys

import numpy as np
import soundfile as sf

SR = 24000


def trim(audio, thresh=0.004, pad=0.04):
    """Remove leading/trailing silence, keep a short natural pad."""
    idx = np.where(np.abs(audio) > thresh)[0]
    if len(idx) == 0:
        return audio
    a = max(0, idx[0] - int(pad * SR))
    b = min(len(audio), idx[-1] + int(pad * SR * 2))
    return audio[a:b]


def main():
    jobs = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    man_path = os.path.join(out, 'manifest.json')
    manifest = json.load(open(man_path)) if os.path.exists(man_path) else {}
    pipes = {}
    for job in jobs:
        key = hashlib.sha1(f"{job['voice']}|{job['speed']}|{job['text']}".encode()).hexdigest()[:16]
        wav = os.path.join(out, key + '.wav')
        if os.path.exists(wav) and job['id'] in manifest and manifest[job['id']].get('key') == key:
            continue
        if not os.path.exists(wav):
            lang = job['voice'][0]                     # 'a' American, 'b' British
            if lang not in pipes:
                from kokoro import KPipeline
                pipes[lang] = KPipeline(lang_code=lang, repo_id='hexgrad/Kokoro-82M')
            chunks, phon = [], []
            for gs, ps, audio in pipes[lang](job['text'], voice=job['voice'], speed=job['speed'],
                                             split_pattern=r'\n+'):
                chunks.append(audio.numpy() if hasattr(audio, 'numpy') else np.asarray(audio))
                phon.append(ps)
            audio = trim(np.concatenate(chunks).astype(np.float32))
            sf.write(wav, audio, SR, subtype='PCM_16')
            phonemes = ' | '.join(phon)
        else:
            phonemes = manifest.get(job['id'], {}).get('phonemes', '')
        info = sf.info(wav)
        manifest[job['id']] = {'key': key, 'file': os.path.basename(wav), 'duration': info.frames / info.samplerate,
                               'text': job['text'], 'voice': job['voice'], 'speed': job['speed'],
                               'phonemes': phonemes}
        print(f"{job['id']:22s} {manifest[job['id']]['duration']:5.2f} s", flush=True)
    json.dump(manifest, open(man_path, 'w'), indent=1)


if __name__ == '__main__':
    main()
