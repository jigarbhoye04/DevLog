import os
import re
from pathlib import Path
import subprocess
import yaml
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src import db

# Sensitive keywords pattern to avoid storing API keys, passwords, etc.
SENSITIVE_PATTERN = re.compile(
    r'(password|secret|key|token|auth|bearer|credentials|\baws_access_key_id\b|\baws_secret_access_key\b)',
    re.IGNORECASE
)

# Common noise commands not worth summarizing
NOISE_COMMANDS = {
    'ls', 'll', 'la', 'cd', 'clear', 'pwd', 'exit', 'history', 'grep', 'cat', 'echo', 'top', 'htop'
}

def get_config() -> dict:
    """Load configuration from ~/.devlog/config.yaml or return defaults."""
    config_path = Path.home() / ".devlog" / "config.yaml"
    if not config_path.exists():
        return {"git_repos": []}
        
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f) or {"git_repos": []}
    except Exception as e:
        print(f"Failed to read config: {e}")
        return {"git_repos": []}

def is_valid_command(cmd: str) -> bool:
    """Filter out noise, excessively short commands, and sensitive commands."""
    cmd = cmd.strip()
    
    # 1. Check if empty or too short
    if not cmd or len(cmd) < 3:
        return False
        
    # 2. Check for exact match against noise list
    base_cmd = cmd.split()[0].lower() if cmd else ""
    if base_cmd in NOISE_COMMANDS and len(cmd.split()) == 1:
        return False
        
    # 3. Check for sensitive keywords
    if SENSITIVE_PATTERN.search(cmd):
        return False
        
    return True

def clean_zsh_history_line(line: str) -> str:
    """Extract just the command from a zsh history line. Format: ': 1678901234:0;command'"""
    if line.startswith(': '):
        parts = line.split(';', 1)
        if len(parts) == 2:
            return parts[1].strip()
    return line.strip()

def collect_shell_history(shell_name: str, lines_to_read: int = 200):
    """Read the last N lines of shell history."""
    history_file = Path.home() / f".{shell_name}_history"
    
    if not history_file.exists():
        return
        
    try:
        # Read the file avoiding decode errors for binary junk
        with open(history_file, 'rb') as f:
            # Simple tail hack reading from end
            f.seek(0, os.SEEK_END)
            buffer = bytearray()
            pointer_location = f.tell()
            lines = []
            
            while pointer_location >= 0 and len(lines) < lines_to_read:
                f.seek(pointer_location)
                pointer_location -= 1
                new_byte = f.read(1)
                
                if new_byte == b'\n':
                    lines.append(buffer[::-1].decode('utf-8', errors='ignore'))
                    buffer = bytearray()
                else:
                    buffer.extend(new_byte)
            
            if buffer:
                lines.append(buffer[::-1].decode('utf-8', errors='ignore'))
                
        # Lines are in reverse chronological order
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if shell_name == 'zsh':
                cmd = clean_zsh_history_line(line)
            else:
                cmd = line
                
            if is_valid_command(cmd):
                db.store_raw_command(f"{shell_name}_history", cmd)
                
    except Exception as e:
        print(f"Error reading {shell_name} history: {e}")

def collect_git_logs():
    """Read recent git commits from tracked repositories."""
    config = get_config()
    repos = config.get("git_repos", [])
    
    for repo_path_str in repos:
        # Expand ~ to actual home dir
        repo_path = Path(repo_path_str).expanduser()
        
        if not repo_path.exists() or not (repo_path / ".git").exists():
            print(f"Warning: Tracked repo {repo_path} does not exist or is not a git repository.")
            continue
            
        try:
            # Get commits from the last 24 hours
            # Format: 'MSG' (we only care about the commit message for learning)
            result = subprocess.run(
                ['git', 'log', '--since="24 hours ago"', '--pretty=format:%s'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            if result.stdout:
                commits = result.stdout.strip().split('\n')
                for commit in commits:
                    commit = commit.strip()
                    if is_valid_command(commit):
                        db.store_raw_command(f"git:{repo_path.name}", f"git commit: {commit}")
                        
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to fetch git log for {repo_path}: {e}")
        except Exception as e:
            print(f"Error accessing git repo {repo_path}: {e}")

def run_collection():
    """Main entrypoint to run all collectors."""
    db.init_db()
    
    # Extract recent commands to seed database with activity
    collect_shell_history('zsh')
    collect_shell_history('bash')
    
    # Read repo activity
    collect_git_logs()
    
if __name__ == "__main__":
    run_collection()
    print("Collection run completed.")
