-- schema.sql
-- This script defines the updated structure of the Krishinetra mission log database,
-- focusing on detailed detection logging for comprehensive analytics.

-- Drop the old table if it exists and the new table for a clean re-initialization.
DROP TABLE IF EXISTS detections;

-- Create the main table for logging every single detection event.
-- This structure is essential for the new detailed analytics dashboard.
CREATE TABLE detections (
    -- A unique ID for every single detection record.
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- The exact time the detection was logged, set automatically. Crucial for time-based analytics.
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- A unique identifier for each mission run (e.g., 'KR-MSN-2025-11-13-001').
    -- This is the primary key for grouping all data by session.
    mission_id TEXT NOT NULL,
    
    -- The sequential number of the plant being scanned within the mission.
    plant_number INTEGER NOT NULL,

    -- The angle/position of the camera when the detection was made.
    -- Expected values: 'top', 'middle', 'bottom'
    scan_angle TEXT NOT NULL,
    
    -- The name of the stress/disease class identified by the YOLO model.
    stress_detected TEXT NOT NULL,
    
    -- The confidence score of the detection from the model (from 0.0 to 1.0).
    confidence REAL NOT NULL,
    
    -- The relative file path to the saved raw image for this specific scan.
    -- This can be NULL if no detection was found (e.g., for a 'Healthy' log).
    image_path TEXT 
);

-- An index on mission_id and timestamp will significantly speed up queries
-- for fetching session-specific data and ordering results, which are common operations
-- for the summary dashboard.
CREATE INDEX idx_mission_timestamp ON detections (mission_id, timestamp);
