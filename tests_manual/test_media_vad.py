"""
Integration Test: Silero VAD via PluginManager

Verifies that the VAD plugin can be loaded, executed via JobQueue,
and return valid MediaAnalysisResult objects over the process boundary.
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Add path to find local libs
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cjm_plugin_system.core.manager import PluginManager
from cjm_plugin_system.core.queue import JobQueue, JobStatus
from cjm_plugin_system.core.scheduling import QueueScheduler

async def run_vad_integration():
    print("=== MEDIA INTEGRATION: SILERO VAD ===")

    # 1. Setup Manager
    manager = PluginManager(scheduler=QueueScheduler())
    manager.discover_manifests()

    plugin_name = "cjm-media-plugin-silero-vad"
    plugin_meta = next((item for item in manager.discovered if item.name == plugin_name), None)

    if not plugin_meta:
        print(f"Plugin {plugin_name} not found. Check manifests.")
        return

    # 2. Load Plugin
    print(f"\n--- Loading Plugin: {plugin_name} ---")
    if not manager.load_plugin(plugin_meta, {"threshold": 0.6}):
        print("Failed to load plugin.")
        return

    # 3. Start Queue
    queue = JobQueue(manager)
    await queue.start()

    # 4. Submit Job
    audio_file = "/mnt/SN850X_8TB_EXT4/Projects/GitHub/cj-mills/cjm-transcription-plugin-voxtral-hf/test_files/02 - 1. Laying Plans.mp3"
    
    if not os.path.exists(audio_file):
        print("Test file not found. Skipping execution.")
        await queue.stop()
        return

    print(f"\n--- Submitting VAD Job ---")
    print(f"File: {os.path.basename(audio_file)}")
    
    job_id = await queue.submit(
        plugin_name,
        media_path=audio_file,
        priority=10
    )
    
    print(f"Job ID: {job_id}")
    
    # 5. Wait for Result
    job = await queue.wait_for_job(job_id, timeout=60)
    
    if job.status == JobStatus.completed:
        result = job.result
        # The result comes back as a Dict from the proxy, or object if deserialized correctly
        # Let's inspect what we got
        print("\n--- Job Completed ---")
        
        # Helper to handle Dict vs Object return
        if isinstance(result, dict):
            ranges = result.get('ranges', [])
            meta = result.get('metadata', {})
        else:
            ranges = result.ranges
            meta = result.metadata
            
        print(f"Segments Detected: {len(ranges)}")
        print(f"Duration: {meta.get('duration', 0):.2f}s")
        print(f"Sample Segment 0: {ranges[0]}")
        
    else:
        print(f"Job Failed: {job.error}")

    # 6. Cleanup
    await queue.stop()
    manager.unload_all()
    print("\n[SUCCESS] Integration test complete.")

if __name__ == "__main__":
    asyncio.run(run_vad_integration())