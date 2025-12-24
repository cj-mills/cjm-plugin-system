# test_whisper_integration.py
from cjm_plugin_system.core.manager import PluginManager

manager = PluginManager()
manager.discover_manifests()

# This should find 'cjm-transcription-plugin-whisper' from the JSON we just made
print("Plugins found:", [p.name for p in manager.discovered])

# Load (Starts subprocess)
manager.load_plugin(manager.discovered[0], {"model": "large-v3", "device": "cuda"})


# Execute (Sends Zero-Copy)
result = manager.execute_plugin(
    "cjm-transcription-plugin-whisper", 
    audio="/mnt/SN850X_8TB_EXT4/Projects/GitHub/cj-mills/cjm-transcription-plugin-whisper/test_files/short_test_audio.mp3"
)

print("Transcription:", result['text'])

import time
time.sleep(20)