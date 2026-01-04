"""
Integration test for the JobQueue.

This test demonstrates:
1. Submitting multiple jobs to the queue
2. Monitoring queue state
3. Cancelling jobs
4. Priority ordering
5. Progress tracking
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


async def test_basic_queue():
    """Test basic queue operations without real plugins."""
    print("=== JOB QUEUE BASIC TEST ===\n")

    # Setup with QueueScheduler for active tracking
    manager = PluginManager(scheduler=QueueScheduler())
    manager.discover_manifests()

    print(f"Discovered {len(manager.discovered)} plugins")

    # Create queue
    queue = JobQueue(manager, max_history=10)

    print("\n--- Queue State (Empty) ---")
    state = queue.get_state()
    print(f"Running: {state['running']}")
    print(f"Pending: {state['pending']}")
    print(f"Stats: {state['stats']}")

    print("\n--- Test Complete ---")


async def test_with_plugins():
    """Test queue with actual plugins (requires installed plugins)."""
    print("=== JOB QUEUE PLUGIN TEST ===\n")

    # Setup
    manager = PluginManager(scheduler=QueueScheduler())
    manager.discover_manifests()

    # Check for system monitor
    sysmon_name = 'cjm-system-monitor-nvidia'
    sysmon_meta = next((m for m in manager.discovered if m.name == sysmon_name), None)

    if not sysmon_meta:
        print(f"System monitor plugin '{sysmon_name}' not found. Skipping plugin test.")
        return

    # Load system monitor
    print("Loading system monitor...")
    if not manager.load_plugin(sysmon_meta):
        print("Failed to load system monitor")
        return
    manager.register_system_monitor(sysmon_name)

    # Check for transcription plugin
    transcription_name = 'cjm-transcription-plugin-whisper'
    transcription_meta = next((m for m in manager.discovered if m.name == transcription_name), None)

    if not transcription_meta:
        print(f"Transcription plugin '{transcription_name}' not found.")
        available = [m.name for m in manager.discovered]
        print(f"Available plugins: {available}")
        manager.unload_all()
        return

    # Load transcription plugin
    print(f"Loading {transcription_name}...")
    if not manager.load_plugin(transcription_meta, {"model": "base", "device": "cuda"}):
        print("Failed to load transcription plugin")
        manager.unload_all()
        return

    # Create and start queue
    queue = JobQueue(manager)
    await queue.start()

    # Test audio file
    test_audio = Path("/mnt/SN850X_8TB_EXT4/Projects/GitHub/cj-mills/cjm-transcription-plugin-whisper/test_files/short_test_audio.mp3")

    if not test_audio.exists():
        print(f"Test audio not found: {test_audio}")
        await queue.stop()
        manager.unload_all()
        return

    print("\n--- Submitting Jobs ---")

    # Submit jobs with different priorities
    job1_id = await queue.submit(transcription_name, audio=str(test_audio), priority=0)
    print(f"Submitted job 1: {job1_id[:8]} (priority=0)")

    job2_id = await queue.submit(transcription_name, audio=str(test_audio), priority=10)
    print(f"Submitted job 2: {job2_id[:8]} (priority=10, should run first)")

    # Check queue state
    print("\n--- Queue State ---")
    state = queue.get_state()
    print(f"Running: {state['running']}")
    print(f"Pending: {len(state['pending'])} jobs")
    for p in state['pending']:
        print(f"  - {p['id'][:8]}: priority={p['priority']}, position={p['position']}")

    # Wait for jobs
    print("\n--- Waiting for Jobs ---")

    job2 = await queue.wait_for_job(job2_id, timeout=120)
    print(f"Job 2 ({job2.id[:8]}): {job2.status.value}")
    if job2.status == JobStatus.completed:
        result_preview = str(job2.result)[:100] if job2.result else "None"
        print(f"  Result: {result_preview}...")

    job1 = await queue.wait_for_job(job1_id, timeout=120)
    print(f"Job 1 ({job1.id[:8]}): {job1.status.value}")
    if job1.status == JobStatus.completed:
        result_preview = str(job1.result)[:100] if job1.result else "None"
        print(f"  Result: {result_preview}...")

    # Final state
    print("\n--- Final Queue State ---")
    state = queue.get_state()
    print(f"Stats: {state['stats']}")

    # Cleanup
    await queue.stop()
    manager.unload_all()

    print("\n--- Test Complete ---")


async def test_cancellation():
    """Test job cancellation."""
    print("=== JOB QUEUE CANCELLATION TEST ===\n")

    manager = PluginManager(scheduler=QueueScheduler())
    manager.discover_manifests()

    # Check for a plugin
    if not manager.discovered:
        print("No plugins discovered. Skipping cancellation test.")
        return

    # Use first available plugin
    plugin_meta = manager.discovered[0]
    print(f"Using plugin: {plugin_meta.name}")

    if not manager.load_plugin(plugin_meta):
        print("Failed to load plugin")
        return

    queue = JobQueue(manager)
    await queue.start()

    # Submit jobs
    job1_id = await queue.submit(plugin_meta.name)
    job2_id = await queue.submit(plugin_meta.name)
    job3_id = await queue.submit(plugin_meta.name)

    print(f"Submitted 3 jobs: {job1_id[:8]}, {job2_id[:8]}, {job3_id[:8]}")

    # Cancel pending job
    print(f"\nCancelling job 3 (pending)...")
    cancelled = await queue.cancel(job3_id)
    print(f"Cancelled: {cancelled}")

    # Check state
    state = queue.get_state()
    print(f"Pending after cancel: {len(state['pending'])}")
    print(f"Cancelled jobs in history: {state['stats']['total_cancelled']}")

    # Cleanup
    await queue.stop()
    manager.unload_all()

    print("\n--- Test Complete ---")


if __name__ == "__main__":
    print("Select test to run:")
    print("1. Basic queue operations (no plugins needed)")
    print("2. Queue with plugins (requires installed plugins)")
    print("3. Cancellation test")
    print("4. Run all tests")

    choice = input("\nEnter choice (1-4): ").strip()

    if choice == "1":
        asyncio.run(test_basic_queue())
    elif choice == "2":
        asyncio.run(test_with_plugins())
    elif choice == "3":
        asyncio.run(test_cancellation())
    elif choice == "4":
        asyncio.run(test_basic_queue())
        print("\n" + "="*50 + "\n")
        asyncio.run(test_with_plugins())
        print("\n" + "="*50 + "\n")
        asyncio.run(test_cancellation())
    else:
        print("Invalid choice")
