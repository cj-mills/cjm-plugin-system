"""
Graph Federation Demo: The "Ingestion" Workflow

This test demonstrates the full lifecycle:
1.  JOB: Transcribe Audio (Voxtral) -> Generates a Job ID
2.  LOGIC: Create Graph Nodes linked to that Job ID (Mocking an LLM extraction)
3.  ACTION: Push Nodes to Context Graph via execute(action=...)
4.  QUERY: Use DuckDB to JOIN the Transcript DB with the Graph DB
"""

import asyncio
import json
import duckdb
import uuid
import sys
import os
import time
from pathlib import Path

# Add path to find local libs
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cjm_plugin_system.core.manager import PluginManager
from cjm_plugin_system.core.queue import JobQueue, JobStatus
from cjm_plugin_system.core.scheduling import QueueScheduler


async def run_graph_federation():
    print("=== GRAPH FEDERATION DEMO: TRANSCRIPT TO KNOWLEDGE GRAPH ===")

    # 1. Setup Manager
    manager = PluginManager(scheduler=QueueScheduler())
    manager.discover_manifests()

    # 2. Identify Plugins
    transcriber_name = "cjm-transcription-plugin-voxtral-hf"
    graph_name = "cjm-graph-plugin-sqlite"

    transcriber_meta = next((item for item in manager.discovered if item.name == transcriber_name), None)
    graph_meta = next((item for item in manager.discovered if item.name == graph_name), None)

    if not transcriber_meta:
        print(f"Plugin {transcriber_name} not found. Check manifests in ~/.cjm/plugins/")
        return

    if not graph_meta:
        print(f"Plugin {graph_name} not found. Check manifests in ~/.cjm/plugins/")
        return

    # 3. Load Plugins (synchronous - load_plugin_async doesn't exist)
    print(f"\n--- Loading Plugins ---")

    # Load Voxtral (CUDA)
    if not manager.load_plugin(transcriber_meta, {"device": "cuda", "model_id": "mistralai/Voxtral-Mini-3B-2507"}):
        print(f"Failed to load {transcriber_name}")
        return
    print(f"  Loaded: {transcriber_name}")

    # Load Graph (CPU/IO)
    if not manager.load_plugin(graph_meta, {"test":"test"}):
        print(f"Failed to load {graph_name}")
        manager.unload_all()
        return
    print(f"  Loaded: {graph_name}")

    # 4. Start Job Queue (For long-running transcription)
    queue = JobQueue(manager)
    await queue.start()

    # 5. EXECUTION PHASE 1: TRANSCRIPTION
    # We define a shared ID that will link the Audio world to the Graph world
    shared_job_id = f"job_{uuid.uuid4().hex[:8]}"
    audio_file = "/mnt/SN850X_8TB_EXT4/Projects/GitHub/cj-mills/cjm-transcription-plugin-whisper/test_files/short_test_audio.mp3"

    print(f"\n--- Phase 1: Transcribing Audio ---")
    print(f"Job ID: {shared_job_id}")

    # Submit to Queue
    queue_job_id = await queue.submit(
        transcriber_name,
        audio=audio_file,
        job_id=shared_job_id,
        priority=10
    )

    # Wait for result
    print("Waiting for transcription...")
    job = await queue.wait_for_job(queue_job_id, timeout=300)

    if job.status != JobStatus.completed:
        print(f"Transcription failed: {job.error}")
        await queue.stop()
        manager.unload_all()
        return

    # job.result is the return value from execute() - typically a dict when going through proxy
    transcript_result = job.result

    # Handle both dict and object cases
    if isinstance(transcript_result, dict):
        transcript_text = transcript_result.get("text", "")
    else:
        transcript_text = transcript_result.text if hasattr(transcript_result, "text") else str(transcript_result)

    print(f"  -> Transcript: {transcript_text[:100]}...")

    # 6. EXECUTION PHASE 2: "MOCK" LLM EXTRACTION
    print(f"\n--- Phase 2: Extracting Entities (Mock) ---")
    # Simulating an LLM analyzing the text and finding entities
    # Crucially, we create a SourceRef pointing back to the specific Transcription Job

    # Create node and edge data as dicts (for JSON transport via execute)
    source_ref_data = {
        "plugin_name": transcriber_name,
        "table_name": "transcriptions",
        "row_id": shared_job_id,
        "segment_slice": "full_text"
    }

    node_a_id = str(uuid.uuid4())
    node_b_id = str(uuid.uuid4())
    edge_id = str(uuid.uuid4())

    node_a_data = {
        "id": node_a_id,
        "label": "Topic",
        "properties": {"name": "Neural Networks", "confidence": 0.95},
        "sources": [source_ref_data]
    }

    node_b_data = {
        "id": node_b_id,
        "label": "Speaker",
        "properties": {"name": "Unknown Expert", "detected_language": "en"},
        "sources": [source_ref_data]
    }

    edge_data = {
        "id": edge_id,
        "source_id": node_b_id,
        "target_id": node_a_id,
        "relation_type": "DISCUSSES",
        "properties": {"sentiment": "neutral"}
    }

    print(f"  Created Node: Topic (Neural Networks)")
    print(f"  Created Node: Speaker (Unknown Expert)")
    print(f"  Created Edge: Speaker --[DISCUSSES]--> Topic")

    # 7. EXECUTION PHASE 3: GRAPH INGESTION
    print(f"\n--- Phase 3: Writing to Context Graph ---")

    # Use manager.execute_plugin_async() with action parameter
    # This is the correct way to call graph operations through the proxy

    print("  -> Adding Nodes...")
    result = await manager.execute_plugin_async(
        graph_name,
        action="add_nodes",
        nodes=[node_a_data, node_b_data]
    )
    print(f"     Result: {result}")

    print("  -> Adding Edge...")
    result = await manager.execute_plugin_async(
        graph_name,
        action="add_edges",
        edges=[edge_data]
    )
    print(f"     Result: {result}")

    # Verify with get_schema
    print("  -> Verifying Graph State...")
    schema = await manager.execute_plugin_async(
        graph_name,
        action="get_schema"
    )
    print(f"     Schema: {schema}")

    # 8. EXECUTION PHASE 4: FEDERATED QUERY
    print(f"\n--- Phase 4: Data Federation (DuckDB) ---")

    db_path_vox = manager.plugins[transcriber_name].manifest['db_path']
    db_path_graph = manager.plugins[graph_name].manifest['db_path']

    print(f"Voxtral DB: {db_path_vox}")
    print(f"Graph DB:   {db_path_graph}")

    # Connect DuckDB
    con = duckdb.connect()

    con.execute(f"ATTACH '{db_path_vox}' AS db_vox (TYPE SQLITE, READ_ONLY TRUE);")
    con.execute(f"ATTACH '{db_path_graph}' AS db_graph (TYPE SQLITE, READ_ONLY TRUE);")

    # The Query: Join Transcript Metadata with Graph Entities
    # We join where the Graph Node's 'sources' array contains the Transcription Job ID
    # Note: DuckDB treats SQLite JSON columns as text.
    # FIX: Use json_extract_string (or ->>) to get the unquoted string for comparison with job_id.

    query = f"""
    SELECT
        t.job_id,
        SUBSTRING(t.text, 1, 80) as transcript_preview,
        n.label as entity_type,
        json_extract_string(n.properties, '$.name') as entity_name,
        e.relation_type
    FROM db_graph.nodes n
    -- Find edges where this node is the source
    LEFT JOIN db_graph.edges e ON n.id = e.source_id
    -- Join to Transcription DB via the sources JSON array
    JOIN db_vox.transcriptions t
      ON json_extract_string(n.sources, '$[0].row_id') = t.job_id
    WHERE t.job_id = '{shared_job_id}'
    """

    try:
        df = con.execute(query).df()

        print("\n=== FEDERATION RESULT ===")
        import pandas as pd
        pd.set_option('display.max_colwidth', None)
        pd.set_option('display.width', 1000)

        if not df.empty:
            print(df.to_string(index=False))
        else:
            print("No linked records found. Check JSON extraction logic.")

            # Debug: Show what's in each table
            print("\n--- Debug: Tables Content ---")
            print("Transcriptions:")
            debug_df = con.execute(f"SELECT job_id, SUBSTRING(text, 1, 50) as text_preview FROM db_vox.transcriptions WHERE job_id = '{shared_job_id}'").df()
            print(debug_df)

            print("\nNodes:")
            debug_df = con.execute("SELECT id, label, sources FROM db_graph.nodes LIMIT 5").df()
            print(debug_df)

    except Exception as e:
        print(f"DuckDB Query Error: {e}")
        import traceback
        traceback.print_exc()

    # Cleanup
    await queue.stop()
    manager.unload_all()
    print("\n--- Demo Complete ---")


if __name__ == "__main__":
    asyncio.run(run_graph_federation())
