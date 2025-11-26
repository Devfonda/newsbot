from pathlib import Path
import hashlib

def load_sent_hashes(path: str):
    p = Path(path)
    if not p.exists():
        return set()
    with p.open('r', encoding='utf-8') as f:
        return {line.strip() for line in f if line.strip()}

def add_sent_hash(path: str, text: str):
    h = hashlib.sha256(text.encode('utf-8')).hexdigest()
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('a', encoding='utf-8') as f:
        f.write(h + '\n')
    return h
