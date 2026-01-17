"""
Integration Test: NLTK Text Processing via PluginManager

Verifies that the NLTK plugin can be loaded, executed via JobQueue,
and correctly handle NLTK data downloads in the isolated process.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add path to find local libs
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cjm_plugin_system.core.manager import PluginManager
from cjm_plugin_system.core.queue import JobQueue, JobStatus
from cjm_plugin_system.core.scheduling import QueueScheduler

async def run_nltk_integration():
    print("=== TEXT INTEGRATION: NLTK SENTENCE SPLITTER ===")

    # 1. Setup Manager
    manager = PluginManager(scheduler=QueueScheduler())
    manager.discover_manifests()

    plugin_name = "cjm-text-plugin-nltk"
    plugin_meta = next((item for item in manager.discovered if item.name == plugin_name), None)

    if not plugin_meta:
        print(f"Plugin {plugin_name} not found. Check manifests.")
        return

    # 2. Load Plugin
    print(f"\n--- Loading Plugin: {plugin_name} ---")
    # This triggers the subprocess spawn and NLTK data check
    if not manager.load_plugin(plugin_meta, {"language": "english"}):
        print("Failed to load plugin.")
        return

    # 3. Start Queue
    queue = JobQueue(manager)
    await queue.start()

    # 4. Submit Job
    raw_text = (
        "Laying Plans Sun Tzu said, The art of war is of vital importance to the state. "
        "It is a matter of life and death, a road either to safety or to ruin. "
        "Hence it is a subject of inquiry which can on no account be neglected."
    )

    print(f"\n--- Submitting Text Job ---")
    print(f"Input Length: {len(raw_text)} chars")
    
    job_id = await queue.submit(
        plugin_name,
        action="split_sentences",
        text=raw_text,
        priority=10
    )
    
    print(f"Job ID: {job_id}")
    
    # 5. Wait for Result
    job = await queue.wait_for_job(job_id, timeout=30)
    
    if job.status == JobStatus.completed:
        result = job.result
        # The proxy returns a Dict for the result
        print("\n--- Job Completed ---")
        
        spans = result.get('spans', [])
        metadata = result.get('metadata', {})
        
        print(f"Tokenizer Used: {metadata.get('tokenizer')}")
        print(f"Sentences Detected: {len(spans)}")
        
        # Verify first sentence
        if len(spans) > 0:
            first = spans[0]
            print(f"Span 0: {first['start_char']}->{first['end_char']} '{first['text'][:20]}...'")
            
            # Verify IPC data integrity
            assert first['text'].startswith("Laying Plans")
            assert first['label'] == "sentence"
        
    else:
        print(f"Job Failed: {job.error}")

    # 6. Cleanup
    await queue.stop()
    manager.unload_all()
    print("\n[SUCCESS] Integration test complete.")

if __name__ == "__main__":
    asyncio.run(run_nltk_integration())