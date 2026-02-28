import subprocess
from pathlib import Path
from datetime import datetime

from src import env
from src.collector import get_config


def _get_authenticated_remote_url() -> str:
    """
    Builds an authenticated HTTPS remote URL using GITHUB_TOKEN from .env.local.
    e.g. https://<token>@github.com/user/devlog-brain.git
    """
    raw_url = env.get("GITHUB_URL") or get_config().get("github", {}).get("remote_url", "")
    token = env.get("GITHUB_TOKEN")

    if not raw_url:
        return ""

    # Inject token into the URL for passwordless push
    if token and raw_url.startswith("https://") and "@" not in raw_url:
        raw_url = raw_url.replace("https://", f"https://{token}@", 1)

    return raw_url


def setup_devlog_repo() -> Path:
    """Ensures the devlog tracked repo is initialized and remote is set."""
    repo_dir = Path.home() / ".devlog" / "repo"
    remote_url = _get_authenticated_remote_url()

    if not repo_dir.exists():
        repo_dir.mkdir(parents=True)
        subprocess.run(['git', 'init'], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(['git', 'checkout', '-b', 'main'], cwd=repo_dir, capture_output=True)

    # Ensure git user config is set (required for commits)
    _ensure_git_user(repo_dir)

    # Always reconcile remote — handles first run and token rotation
    if remote_url:
        existing = subprocess.run(
            ['git', 'remote'], cwd=repo_dir, capture_output=True, text=True
        )
        if 'origin' in existing.stdout.splitlines():
            subprocess.run(['git', 'remote', 'set-url', 'origin', remote_url], cwd=repo_dir, capture_output=True)
        else:
            subprocess.run(['git', 'remote', 'add', 'origin', remote_url], cwd=repo_dir, capture_output=True)

    return repo_dir


def _ensure_git_user(repo_dir: Path):
    """Sets a local git user.name and user.email if not already configured."""
    name_check = subprocess.run(
        ['git', 'config', 'user.name'], cwd=repo_dir, capture_output=True, text=True
    )
    if not name_check.stdout.strip():
        subprocess.run(['git', 'config', 'user.name', 'DevLog Bot'], cwd=repo_dir, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'devlog@local'], cwd=repo_dir, capture_output=True)


def save_daily_markdown(markdown_content: str) -> Path:
    """Saves the markdown blob to the date-mapped directory structure."""
    repo_dir = setup_devlog_repo()

    now = datetime.now()
    year_dir = repo_dir / str(now.year)
    year_dir.mkdir(exist_ok=True)

    file_path = year_dir / f"{now.strftime('%m-%d')}.md"
    file_path.write_text(markdown_content, encoding='utf-8')
    return file_path


def git_commit_and_push():
    """Commits all staged changes and pushes to the configured remote."""
    repo_dir = setup_devlog_repo()

    try:
        subprocess.run(['git', 'add', '.'], cwd=repo_dir, check=True, capture_output=True)

        now = datetime.now()
        commit_msg = f"DevLog auto-update: {now.strftime('%Y-%m-%d')}"
        result = subprocess.run(
            ['git', 'commit', '-m', commit_msg],
            cwd=repo_dir, capture_output=True, text=True
        )

        if result.returncode != 0 and "nothing to commit" in result.stdout:
            print("Nothing new to commit.")
            return

        print(f"Committed: {commit_msg}")

        remote_url = _get_authenticated_remote_url()
        if remote_url:
            print("Pushing to GitHub...")
            # First attempt a pull --rebase to fetch any remote initial commits (like a README)
            subprocess.run(
                ['git', 'pull', '--rebase', 'origin', 'main'],
                cwd=repo_dir, capture_output=True
            )
            
            push = subprocess.run(
                ['git', 'push', '--set-upstream', 'origin', 'main'],
                cwd=repo_dir, capture_output=True, text=True
            )
            if push.returncode != 0:
                print(f"Push failed: {push.stderr.strip()}")
            else:
                print("Push complete ✅")

    except subprocess.CalledProcessError as e:
        print(f"Git operation failed: {e.stderr}")


def trigger_daily_sync():
    """Main entrypoint for `devlog push`: collect, summarize, commit, push."""
    from src import db, ai, collector
    from src.utils import Colors

    print(f"\n{Colors.CYAN}→ Collecting shell history and git logs...{Colors.ENDC}")
    collector.run_collection()

    raw_commands = db.get_unprocessed_commands()
    command_strings = [c['command'] for c in raw_commands]

    learnings = db.get_learnings_since(1)
    learning_strings = [l['content'] for l in learnings]

    print(f"{Colors.CYAN}→ Generating AI summary ({len(command_strings)} commands, {len(learning_strings)} learnings)...{Colors.ENDC}")
    summary_md = ai.generate_daily_summary(command_strings, learning_strings)

    file_path = save_daily_markdown(summary_md)
    print(f"{Colors.GREEN}→ Saved to {file_path}{Colors.ENDC}")

    db.mark_commands_processed([c['id'] for c in raw_commands])

    git_commit_and_push()

    print(f"\n{Colors.BOLD}{Colors.GREEN}Daily sync completed.{Colors.ENDC}\n")
