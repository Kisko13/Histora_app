from pathlib import Path
import shutil

ROOT = Path.cwd()
SRC = Path(__file__).parent

def copy(src, dst):
    src = Path(src).resolve()
    dst = Path(dst).resolve()

    if src == dst:
        print(f"Skipping {src.name} (already in place)")
        return

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

copy('hps/core/v38_voice_providers.py', 'hps/core/v38_voice_providers.py')

# Add env examples without overwriting existing values.
env = ROOT / '.env'
text = env.read_text(encoding='utf-8', errors='ignore') if env.exists() else ''
add = []
for line in [
    '# V38 real voice provider chain',
    'VOICE_PROVIDER_CHAIN=qwen,piper,kokoro,mock',
    '# PIPER_EXE=C:\\tools\\piper\\piper.exe',
    '# PIPER_MODEL=C:\\tools\\piper\\voices\\en_US-lessac-medium.onnx',
    '# KOKORO_CMD=python C:\\tools\\kokoro\\tts.py --input {text_file} --output {out_file}',
    'TTS_TIMEOUT_SEC=240',
]:
    key = line.split('=',1)[0].strip('# ').strip()
    if '=' in line and key and key not in text:
        add.append(line)
    elif line.startswith('# V38') and line not in text:
        add.append(line)
if add:
    env.write_text(text.rstrip() + '\n\n' + '\n'.join(add) + '\n', encoding='utf-8')
    print('updated .env with V38 provider settings')

print('\nV38 provider foundation installed.')
print('Next: wire Generate Voice Queue to hps.core.v38_voice_providers.generate_with_chain(...)')
