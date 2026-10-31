# Model weights go here

The weights are too large for git (about 3 GB), so they are not in this repo.
Download them from Hugging Face into this folder:

    models/Ming-3.0-tts-0.5B/

- Page: https://huggingface.co/inclusionAI/Ming-3.0-tts-0.5B/tree/main (MIT, no login needed)
- Tested revision: `7247f4c94a5b2e987404ed28a5cfec41b1a4ca61`

Command line (after `setup.bat`):

    .venv\Scripts\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download('inclusionAI/Ming-3.0-tts-0.5B', revision='7247f4c94a5b2e987404ed28a5cfec41b1a4ca61', local_dir=r'models\Ming-3.0-tts-0.5B')"

Check afterwards: `model.safetensors` must be 2,959,055,504 bytes. `.venv\Scripts\python.exe check.py`
verifies this. Full steps are in SETUP.md, section 4.
