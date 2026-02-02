# services/database_manager.py

import sqlite3
import logging
import os
import sys
from typing import List, Dict, Any, Optional

# This allows importing the config file from the project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import config

logger = logging.getLogger(__name__)

def get_db_connection() -> sqlite3.Connection:
    """
    Establishes a connection to the SQLite database.
    Configures the connection to return rows that behave like dictionaries.
    """
    try:
        conn = sqlite3.connect(config.DATABASE_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row # Allows accessing columns by name
        return conn
    except sqlite3.Error as e:
        logger.critical(f"Database connection failed: {e}", exc_info=True)
        raise


def init_db():
    """
    Initializes the database using schema.sql, but ONLY if the database file
    does not already exist. This prevents data from being wiped on every restart.
    """
    # The fix is to only create the database if the file does not exist.
    if os.path.exists(config.DATABASE_PATH):
        logger.info(f"Database already exists at {config.DATABASE_PATH}. Skipping initialization.")
        return

    # If the file doesn't exist, create it from the schema.
    try:
        logger.warning(f"Database not found. Creating new database at {config.DATABASE_PATH}")
        conn = get_db_connection()
        schema_path = os.path.join(config.PROJECT_ROOT, 'schema.sql')
        with open(schema_path, 'r') as f:
            conn.executescript(f.read())
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully.")
    except FileNotFoundError:
        logger.critical(f"CRITICAL: schema.sql not found at {schema_path}. Cannot initialize database.")
    except sqlite3.Error as e:
        logger.critical(f"Database initialization failed: {e}", exc_info=True)
        

def log_detection(mission_id: str, plant_number: int, scan_angle: str, stress_detected: str, confidence: float, image_path: str):
    """
    Logs a single detection event to the new 'detections' table.
    """
    sql = ''' INSERT INTO detections(mission_id, plant_number, scan_angle, stress_detected, confidence, image_path)
              VALUES(?,?,?,?,?,?) '''
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(sql, (mission_id, plant_number, scan_angle, stress_detected, confidence, image_path))
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        logger.error(f"Failed to log detection to database: {e}", exc_info=True)


def get_latest_mission_id(exclude_id: Optional[str] = None) -> Optional[str]:
    """
    Finds the ID of the mission with the most recent timestamp in the database.
    Optionally excludes a given mission_id (used to find the one *before* an active mission).
    """
    conn = get_db_connection()
    query = "SELECT mission_id FROM detections WHERE (?1 IS NULL OR mission_id != ?1) GROUP BY mission_id ORDER BY MAX(timestamp) DESC LIMIT 1"
    
    try:
        mission = conn.execute(query, (exclude_id,)).fetchone()
        return mission['mission_id'] if mission else None
    except sqlite3.Error as e:
        logger.error(f"Could not query for latest mission ID: {e}")
        return None
    finally:
        conn.close()


def get_previous_session_analytics(mission_id: str) -> Dict[str, Any]:
    """
    Gathers all statistics and data points for a specific previous mission.
    """
    if not mission_id:
        return {"error": "No mission ID provided."}
        
    conn = get_db_connection()
    
    header_query = """
        SELECT
            MIN(timestamp) as start_time, MAX(timestamp) as end_time,
            COUNT(DISTINCT plant_number) as total_plants_scanned
        FROM detections WHERE mission_id = ?
    """
    header_data = conn.execute(header_query, (mission_id,)).fetchone()
    
    summary_query = "SELECT stress_detected, COUNT(*) as count FROM detections WHERE mission_id = ? GROUP BY stress_detected ORDER BY count DESC"
    summary_data = conn.execute(summary_query, (mission_id,)).fetchall()
    
    plant_bar_chart_query = """
        SELECT plant_number, stress_detected, COUNT(*) as count
        FROM detections WHERE mission_id = ? AND stress_detected != 'Healthy'
        GROUP BY plant_number, stress_detected ORDER BY plant_number
    """
    plant_bar_chart_data = conn.execute(plant_bar_chart_query, (mission_id,)).fetchall()

    conn.close()

    total_plants = header_data['total_plants_scanned'] if header_data and header_data['total_plants_scanned'] else 0
    health_index = 100.0
    if total_plants > 0:
        conn = get_db_connection()
        diseased_plants_query = "SELECT COUNT(DISTINCT plant_number) as count FROM detections WHERE mission_id = ? AND stress_detected != 'Healthy'"
        diseased_plants_count = conn.execute(diseased_plants_query, (mission_id,)).fetchone()['count']
        conn.close()
        
        healthy_plants_count = total_plants - diseased_plants_count
        health_index = (healthy_plants_count / total_plants) * 100

    return {
        "header_stats": dict(header_data) if header_data else {},
        "detection_summary": [dict(row) for row in summary_data],
        "plant_disease_data": [dict(row) for row in plant_bar_chart_data],
        "health_index": round(health_index, 1)
    }

def get_overall_analytics() -> Dict[str, Any]:
    """
    Gathers aggregated statistics across all missions recorded in the database.
    """
    conn = get_db_connection()
    
    agg_query = """
        SELECT
            COUNT(DISTINCT mission_id) as total_missions,
            COUNT(DISTINCT mission_id || '-' || plant_number) as total_plants_scanned,
            SUM(CASE WHEN stress_detected != 'Healthy' THEN 1 ELSE 0 END) as total_detections
        FROM detections
    """
    agg_data = conn.execute(agg_query).fetchone()

    overall_summary_query = "SELECT stress_detected, COUNT(*) as count FROM detections GROUP BY stress_detected ORDER BY count DESC"
    overall_summary = conn.execute(overall_summary_query).fetchall()

    session_health_query = """
        WITH SessionPlants AS (SELECT DISTINCT mission_id, plant_number, DATE(timestamp) as mission_date FROM detections),
        DiseasedPlants AS (SELECT DISTINCT mission_id, plant_number FROM detections WHERE stress_detected != 'Healthy')
        SELECT sp.mission_id, sp.mission_date,
               COUNT(sp.plant_number) - COUNT(dp.plant_number) as healthy_count,
               COUNT(dp.plant_number) as diseased_count
        FROM SessionPlants sp LEFT JOIN DiseasedPlants dp ON sp.mission_id = dp.mission_id AND sp.plant_number = dp.plant_number
        GROUP BY sp.mission_id ORDER BY sp.mission_date
    """
    session_health_data = conn.execute(session_health_query).fetchall()

    trend_query = """
        SELECT DATE(timestamp) as date, stress_detected, COUNT(*) as count
        FROM detections WHERE stress_detected != 'Healthy'
        GROUP BY date, stress_detected ORDER BY date
    """
    trend_data = conn.execute(trend_query).fetchall()
    conn.close()

    total_plants = agg_data['total_plants_scanned'] if agg_data else 0
    overall_health_index = 100.0
    if total_plants > 0:
        conn = get_db_connection()
        total_diseased_plants_query = "SELECT COUNT(DISTINCT mission_id || '-' || plant_number) as count FROM detections WHERE stress_detected != 'Healthy'"
        total_diseased_count = conn.execute(total_diseased_plants_query).fetchone()['count']
        conn.close()
        overall_health_index = ((total_plants - total_diseased_count) / total_plants) * 100

    most_frequent = "N/A"
    if overall_summary:
        non_healthy_detections = [s for s in overall_summary if s['stress_detected'] != 'Healthy']
        if non_healthy_detections:
            total_disease_count = sum(s['count'] for s in non_healthy_detections)
            most_frequent_disease = non_healthy_detections[0]
            most_frequent_perc = (most_frequent_disease['count'] / total_disease_count) * 100
            most_frequent = f"{most_frequent_disease['stress_detected'].replace('_', ' ')} ({most_frequent_perc:.0f}%)"

    final_agg_data = dict(agg_data) if agg_data else {}
    final_agg_data['health_index'] = round(overall_health_index, 1)
    final_agg_data['most_frequent_disease'] = most_frequent

    return {
        "aggregated_stats": final_agg_data,
        "overall_detection_summary": [dict(row) for row in overall_summary],
        "session_health_data": [dict(row) for row in session_health_data],
        "disease_trend_data": [dict(row) for row in trend_data]
    }

