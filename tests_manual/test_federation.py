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

async def run_comparison():
    print("=== FEDERATION DEMO: MODEL ARENA ===")
    
    # 1. Setup Manager
    manager = PluginManager()
    manager.discover_manifests()

    # This spins up the lightweight 'test-sys-mon' environment
    print("\n--- Starting System Monitor ---")
    sysmon_plugin_name = 'cjm-system-monitor-nvidia'
    sysmon_plugin_meta = next((item for item in manager.discovered if item.name == sysmon_plugin_name), None)
    if not manager.load_plugin(sysmon_plugin_meta):
        print("❌ Failed to load monitor")
        return
    manager.register_system_monitor(sysmon_plugin_name)

    # Verify we can see Real Hardware Stats
    stats = await manager._get_global_stats_async()
    print(f"✅ Real-Time System Stats: {json.dumps(stats, indent=2)}")
    
    # 2. Identify our Contenders
    # Replace these names with your actual installed plugins
    plugin_a_name = "cjm-transcription-plugin-whisper"
    plugin_b_name = "cjm-transcription-plugin-voxtral-hf" # Or your second plugin

    plugin_a_meta = next((item for item in manager.discovered if item.name == plugin_a_name), None)
    manager.load_plugin(plugin_a_meta, {"model": "large-v3", "device": "cuda"})

    plugin_b_meta = next((item for item in manager.discovered if item.name == plugin_b_name), None)
    manager.load_plugin(plugin_b_meta, {"device": "cuda"})

    
    if plugin_b_name not in manager.plugins:
        print(f"⚠️ Second plugin {plugin_b_name} not found. Skipping execution step.")
        # Proceeding just to show DuckDB logic if DBs existed, or exit
        return

    # 3. Define a Shared Job ID
    # This acts as the foreign key linking the two isolated databases
    job_id = f"demo_{uuid.uuid4().hex[:8]}"
    audio_file = "/mnt/SN850X_8TB_EXT4/Projects/GitHub/cj-mills/cjm-transcription-plugin-whisper/test_files/short_test_audio.mp3"
    
    print(f"🚀 Job ID: {job_id}")
    print(f"🎧 Processing: {audio_file}")

    # 4. Launch Jobs in Parallel (Async)
    # FastHTML would do this to keep the UI responsive
    print("... Running Models (this may take a moment) ...")
    
    # We pass 'job_id' in kwargs. The updated _save_to_db will use it.
    results = await asyncio.gather(
        manager.execute_plugin_async(plugin_a_name, audio=audio_file, job_id=job_id),
        manager.execute_plugin_async(plugin_b_name, audio=audio_file, job_id=job_id)
    )
    
    print("✅ Inference Complete.")

    # 5. Data Federation (The Magic Step)
    # We fetch the DB paths from the manifest metadata
    db_path_a = manager.plugins[plugin_a_name].manifest['db_path']
    db_path_b = manager.plugins[plugin_b_name].manifest['db_path']
    
    print(f"\n📊 Attaching Databases:")
    print(f"   A: {db_path_a}")
    print(f"   B: {db_path_b}")

    # Connect DuckDB
    con = duckdb.connect()
    
    # Attach Read-Only (Safe for concurrent use)
    con.execute(f"ATTACH '{db_path_a}' AS db_whisper (TYPE SQLITE, READ_ONLY TRUE);")
    con.execute(f"ATTACH '{db_path_b}' AS db_voxtral (TYPE SQLITE, READ_ONLY TRUE);")
    
    # 6. Run Federated Query
    # Join the two completely separate databases on job_id
    query = f"""
    SELECT 
        w.job_id,
        w.created_at,
        w.text as whisper_text,
        v.text as voxtral_text
    FROM db_whisper.transcriptions w
    JOIN db_voxtral.transcriptions v 
      ON w.job_id = v.job_id
    WHERE w.job_id = '{job_id}'
    """
    
    df = con.execute(query).df()
    
    # 7. Display Result
    print("\n🏆 COMPARISON RESULT (Pandas DataFrame):")
    print("-" * 60)
    # Adjust display options
    import pandas as pd
    pd.set_option('display.max_colwidth', None)
    
    if not df.empty:
        print(f"Whisper: {df.iloc[0]['whisper_text'][:100]}...")
        print("-" * 20)
        print(f"Voxtral: {df.iloc[0]['voxtral_text'][:100]}...")
    else:
        print("❌ No matching records found. Check if _save_to_db worked.")

    manager.unload_all()

if __name__ == "__main__":
    asyncio.run(run_comparison())