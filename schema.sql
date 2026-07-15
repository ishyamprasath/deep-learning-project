-- schema.sql
-- SQLite schema for Drone Intelligence Application

CREATE TABLE IF NOT EXISTS system_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    agent_name TEXT,
    log_level TEXT,
    message TEXT
);

CREATE TABLE IF NOT EXISTS gps_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    lat REAL,
    lon REAL,
    alt REAL,
    quality TEXT,
    source TEXT
);

CREATE TABLE IF NOT EXISTS threat_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    type TEXT,
    confidence REAL,
    details TEXT,
    status TEXT,
    lat REAL,
    lon REAL
);

CREATE TABLE IF NOT EXISTS obstacle_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    distance REAL,
    angle REAL,
    status TEXT,
    action TEXT
);

CREATE TABLE IF NOT EXISTS telemetry_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    speed REAL,
    altitude REAL,
    battery REAL,
    heading REAL
);
