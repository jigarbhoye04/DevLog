import os
import sqlite3
from pathlib import Path
from datetime import datetime
import json
import logging

DB_DIR = Path.home() / ".devlog"
DB_PATH = DB_DIR / "devlog.db"

def init_db():
    """Initializes the SQLite database and creates tables if they do not exist."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Table for manual learnings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS learnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            tags TEXT DEFAULT '[]',
            last_reviewed DATETIME DEFAULT CURRENT_TIMESTAMP,
            review_count INTEGER DEFAULT 0
        )
    ''')
    
    # Table for scraped shell/git commands to be summarized
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            command TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            processed BOOLEAN DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()

def add_learning(content: str, tags: list = None) -> int:
    """Adds a new learning directly to the database."""
    if tags is None:
        tags = []
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO learnings (content, tags) VALUES (?, ?)",
        (content, json.dumps(tags))
    )
    
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return row_id

def get_due_flashcard() -> dict | None:
    """Retrieves a single learning that is due for review (>3 days old)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get a learning where last_reviewed is older than 3 days, order by oldest first
    cursor.execute('''
        SELECT * FROM learnings 
        WHERE julianday('now') - julianday(last_reviewed) > 3
        ORDER BY last_reviewed ASC
        LIMIT 1
    ''')
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def mark_flashcard_reviewed(learning_id: int):
    """Updates the last_reviewed timestamp for a learning."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE learnings 
        SET last_reviewed = CURRENT_TIMESTAMP,
            review_count = review_count + 1
        WHERE id = ?
    ''', (learning_id,))
    
    conn.commit()
    conn.close()

def get_learnings_since(days=1) -> list[dict]:
    """Retrieves all learnings added in the last X days."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM learnings 
        WHERE julianday('now') - julianday(timestamp) <= ?
        ORDER BY timestamp DESC
    ''', (days,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def store_raw_command(source: str, command: str):
    """Stores a raw command from shell history or git log."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Avoid duplicate unprocessed commands
    cursor.execute('''
        SELECT id FROM commands 
        WHERE command = ? AND processed = 0
    ''', (command,))
    
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO commands (source, command) VALUES (?, ?)",
            (source, command)
        )
        
    conn.commit()
    conn.close()

def get_unprocessed_commands() -> list[dict]:
    """Retrieves all raw commands that haven't been summarized yet."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM commands 
        WHERE processed = 0
        ORDER BY timestamp ASC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def mark_commands_processed(command_ids: list[int]):
    """Marks a list of commands as processed."""
    if not command_ids:
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    placeholders = ','.join(['?'] * len(command_ids))
    cursor.execute(f'''
        UPDATE commands 
        SET processed = 1
        WHERE id IN ({placeholders})
    ''', command_ids)
    
    conn.commit()
    conn.close()

def search_learnings(keyword: str) -> list[dict]:
    """Search for learnings matching keyword."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM learnings 
        WHERE content LIKE ?
        ORDER BY timestamp DESC
    ''', (f'%{keyword}%',))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def get_all_logged_dates() -> list[str]:
    """Returns all distinct dates (YYYY-MM-DD) that have at least one learning."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT DISTINCT date(timestamp) as day
        FROM learnings
        ORDER BY day DESC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    return [row[0] for row in rows]

def get_learnings_by_date(date_str: str) -> list[dict]:
    """Returns all learnings for a specific date (YYYY-MM-DD)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM learnings
        WHERE date(timestamp) = ?
        ORDER BY timestamp ASC
    ''', (date_str,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]
