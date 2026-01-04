"""
Federation Demo: Model Arena with JobQueue

This test demonstrates:
1. Using JobQueue to manage transcription jobs
2. Sequential execution respecting GPU resources
3. Queue state visibility during execution
4. Data federation via DuckDB across plugin databases
"""

import asyncio
import json
import duckdb
import uuid
import sys
import os
from pathlib import Path

# Add path to find local libs
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cjm_plugin_system.core.manager import PluginManager
from cjm_plugin_system.core.queue import JobQueue, JobStatus
from cjm_plugin_system.core.scheduling import QueueScheduler


async def run_comparison():
    print("=== FEDERATION DEMO: MODEL ARENA (with JobQueue) ===")

    # 1. Setup Manager with QueueScheduler for active tracking
    manager = PluginManager(scheduler=QueueScheduler())
    manager.discover_manifests()

    # Load System Monitor
    print("\n--- Starting System Monitor ---")
    sysmon_plugin_name = 'cjm-system-monitor-nvidia'
    sysmon_plugin_meta = next((item for item in manager.discovered if item.name == sysmon_plugin_name), None)
    if not sysmon_plugin_meta or not manager.load_plugin(sysmon_plugin_meta):
        print("Failed to load system monitor")
        return
    manager.register_system_monitor(sysmon_plugin_name)

    # Verify system stats
    stats = await manager._get_global_stats_async()
    print(f"Real-Time System Stats: {json.dumps(stats, indent=2)}")

    # 2. Identify our Contenders
    plugin_a_name = "cjm-transcription-plugin-whisper"
    plugin_b_name = "cjm-transcription-plugin-voxtral-hf"

    plugin_a_meta = next((item for item in manager.discovered if item.name == plugin_a_name), None)
    plugin_b_meta = next((item for item in manager.discovered if item.name == plugin_b_name), None)

    if not plugin_a_meta:
        print(f"Plugin {plugin_a_name} not found")
        manager.unload_all()
        return

    if not plugin_b_meta:
        print(f"Plugin {plugin_b_name} not found")
        manager.unload_all()
        return

    # Load plugins
    print(f"\n--- Loading Plugins ---")
    manager.load_plugin(plugin_a_meta, {"model": "large-v3", "device": "cuda"})
    manager.load_plugin(plugin_b_meta, {"device": "cuda"})

    # 3. Create and Start JobQueue
    print("\n--- Starting Job Queue ---")
    queue = JobQueue(manager)
    await queue.start()

    # 4. Define Shared Job ID for Database Federation
    # This acts as the foreign key linking the two isolated databases
    db_job_id = f"demo_{uuid.uuid4().hex[:8]}"
    audio_file = "/mnt/SN850X_8TB_EXT4/Projects/GitHub/cj-mills/cjm-transcription-plugin-whisper/test_files/short_test_audio.mp3"

    print(f"\nDB Job ID: {db_job_id}")
    print(f"Audio: {audio_file}")

    # 5. Submit Jobs to Queue
    print("\n--- Submitting Jobs ---")

    # Submit Whisper job (priority=10, runs first)
    job_a_id = await queue.submit(
        plugin_a_name,
        audio=audio_file,
        job_id=db_job_id,
        priority=10
    )
    print(f"Submitted {plugin_a_name}: {job_a_id[:8]} (priority=10)")

    # Submit Voxtral job (priority=0, runs second after Whisper frees GPU)
    job_b_id = await queue.submit(
        plugin_b_name,
        audio=audio_file,
        job_id=db_job_id,
        priority=0
    )
    print(f"Submitted {plugin_b_name}: {job_b_id[:8]} (priority=0)")

    # 6. Show Queue State
    print("\n--- Queue State ---")
    state = queue.get_state()
    if state['running']:
        print(f"Running: {state['running']['plugin_name']} ({state['running']['id'][:8]})")
    print(f"Pending: {len(state['pending'])} jobs")
    for p in state['pending']:
        print(f"  - {p['plugin_name']}: priority={p['priority']}, position={p['position']}")

    # 7. Wait for Jobs with Progress Updates
    print("\n--- Processing Jobs ---")

    # Wait for Whisper job
    print(f"Waiting for {plugin_a_name}...")
    job_a = await queue.wait_for_job(job_a_id, timeout=300)
    if job_a.status == JobStatus.completed:
        print(f"  Completed in {job_a.completed_at - job_a.started_at:.1f}s")
    else:
        print(f"  {job_a.status.value}: {job_a.error}")

    # Wait for Voxtral job
    print(f"Waiting for {plugin_b_name}...")
    job_b = await queue.wait_for_job(job_b_id, timeout=300)
    if job_b.status == JobStatus.completed:
        print(f"  Completed in {job_b.completed_at - job_b.started_at:.1f}s")
    else:
        print(f"  {job_b.status.value}: {job_b.error}")

    # 8. Show Final Queue Stats
    print("\n--- Final Queue Stats ---")
    state = queue.get_state()
    print(f"Completed: {state['stats']['total_completed']}")
    print(f"Failed: {state['stats']['total_failed']}")
    print(f"Cancelled: {state['stats']['total_cancelled']}")

    # 9. Stop Queue
    await queue.stop()

    # 10. Data Federation (The Magic Step)
    if job_a.status != JobStatus.completed or job_b.status != JobStatus.completed:
        print("\nSkipping federation - not all jobs completed successfully")
        manager.unload_all()
        return

    db_path_a = manager.plugins[plugin_a_name].manifest['db_path']
    db_path_b = manager.plugins[plugin_b_name].manifest['db_path']

    print(f"\n--- Data Federation ---")
    print(f"Whisper DB: {db_path_a}")
    print(f"Voxtral DB: {db_path_b}")

    # Connect DuckDB and attach plugin databases
    con = duckdb.connect()
    con.execute(f"ATTACH '{db_path_a}' AS db_whisper (TYPE SQLITE, READ_ONLY TRUE);")
    con.execute(f"ATTACH '{db_path_b}' AS db_voxtral (TYPE SQLITE, READ_ONLY TRUE);")

    # Federated query joining databases on job_id
    query = f"""
    SELECT
        w.job_id,
        w.created_at,
        w.text as whisper_text,
        v.text as voxtral_text
    FROM db_whisper.transcriptions w
    JOIN db_voxtral.transcriptions v
      ON w.job_id = v.job_id
    WHERE w.job_id = '{db_job_id}'
    """

    df = con.execute(query).df()

    # 11. Display Comparison Result
    print("\n--- Comparison Result ---")
    print("-" * 60)

    import pandas as pd
    pd.set_option('display.max_colwidth', None)

    if not df.empty:
        print(f"Whisper: {df.iloc[0]['whisper_text'][:100]}...")
        print("-" * 20)
        print(f"Voxtral: {df.iloc[0]['voxtral_text'][:100]}...")
    else:
        print("No matching records found. Check if plugins saved to database.")

    # Cleanup
    manager.unload_all()
    print("\n--- Demo Complete ---")


if __name__ == "__main__":
    asyncio.run(run_comparison())
