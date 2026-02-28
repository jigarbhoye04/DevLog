import argparse
import json
import sys
from pathlib import Path

# Add src to Python path so we can run directly from the repo
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src import db

def handle_learn(args):
    """Handles the 'learn' command."""
    if not args.content:
        from src.utils import Colors
        print(f"{Colors.RED}Error: Learning content is required.{Colors.ENDC}")
        sys.exit(1)
        
    tags = args.tags.split(',') if args.tags else []
    
    # Initialize DB if not exists
    db.init_db()
    
    try:
        from src.utils import Colors
        row_id = db.add_learning(args.content, tags)
        print(f"\n✅ {Colors.GREEN}Added learning #{row_id} successfully.{Colors.ENDC}\n")
    except Exception as e:
        print(f"Failed to add learning: {e}")
        sys.exit(1)

def handle_today(args):
    """Handles the 'today' command."""
    db.init_db()
    
    try:
        from src.utils import Colors, print_header
        
        learnings = db.get_learnings_since(1)
        print_header("Today's Engineering Log")
        
        if not learnings:
            print(f"  {Colors.YELLOW}No explicit learnings added today yet. Use 'devlog learn' to add one!{Colors.ENDC}\n")
            return
            
        for idx, l in enumerate(learnings, 1):
            tags_disp = ', '.join(json.loads(l['tags'])) if l['tags'] else 'uncategorized'
            print(f"  {Colors.GREEN}{idx}.{Colors.ENDC} {l['content']}")
            if tags_disp != 'uncategorized':
                 print(f"     {Colors.YELLOW}🏷️  {tags_disp}{Colors.ENDC}")
            print()
            
    except Exception as e:
        print(f"Failed to fetch today's learnings: {e}")
        sys.exit(1)

def handle_push(args):
    """Handles the 'push' command."""
    from src import github_sync
    print("Triggering daily sync pipeline...")
    github_sync.trigger_daily_sync()

def handle_quiz(args):
    """Handles the 'quiz' command."""
    db.init_db()
    
    try:
        from src.utils import print_box, Colors
        
        flashcard = db.get_due_flashcard()
        if not flashcard:
            if not args.auto:
                print(f"\n✨ {Colors.GREEN}No learnings are due for review. You're all caught up!{Colors.ENDC} ✨\n")
            return
            
        tags_list = json.loads(flashcard['tags']) if flashcard['tags'] else []
        tags_str = ", ".join(tags_list)
        
        print_box("DevLog Flashcard", flashcard['content'], tags_str)
        
        if not args.auto:
            input(f"  {Colors.BOLD}Press Enter to mark as reviewed...{Colors.ENDC}")
        
        db.mark_flashcard_reviewed(flashcard['id'])
        
        if not args.auto:
            print(f"  ✅ {Colors.GREEN}Marked as reviewed. Keep it up!{Colors.ENDC}\n")
            
    except Exception as e:
        if not args.auto:
            print(f"Failed to load quiz: {e}")
            sys.exit(1)

def handle_search(args):
    """Handles the 'search' command."""
    db.init_db()
    
    try:
        from src.utils import Colors, print_header
        
        results = db.search_learnings(args.keyword)
        print_header(f"Search: '{args.keyword}'")
        
        if not results:
            print(f"  {Colors.YELLOW}No learnings found.{Colors.ENDC}\n")
            return
            
        print(f"  {Colors.CYAN}{len(results)} result(s) found{Colors.ENDC}\n")
        for idx, l in enumerate(results, 1):
            tags_list = json.loads(l['tags']) if l['tags'] else []
            tags_disp = ', '.join(tags_list) if tags_list else ''
            ts = l['timestamp'][:10] if l.get('timestamp') else ''
            print(f"  {Colors.GREEN}{idx}.{Colors.ENDC} {l['content']}")
            meta_parts = []
            if ts:
                meta_parts.append(ts)
            if tags_disp:
                meta_parts.append(f"🏷️  {tags_disp}")
            if meta_parts:
                print(f"     {Colors.YELLOW}{' · '.join(meta_parts)}{Colors.ENDC}")
            print()
    except Exception as e:
        print(f"Failed to search learnings: {e}")
        sys.exit(1)

def handle_history(args):
    """Handles the 'history' command — browse past memories by date."""
    db.init_db()
    
    try:
        from src.utils import Colors, print_header
        
        if args.date:
            # Show learnings for a specific date
            learnings = db.get_learnings_by_date(args.date)
            print_header(f"DevLog — {args.date}")
            
            if not learnings:
                print(f"  {Colors.YELLOW}No learnings recorded on {args.date}.{Colors.ENDC}\n")
                return
                
            for idx, l in enumerate(learnings, 1):
                tags_list = json.loads(l['tags']) if l['tags'] else []
                tags_disp = ', '.join(tags_list) if tags_list else ''
                print(f"  {Colors.GREEN}{idx}.{Colors.ENDC} {l['content']}")
                if tags_disp:
                    print(f"     {Colors.YELLOW}🏷️  {tags_disp}{Colors.ENDC}")
                print()
        else:
            # Show all days with logged learnings
            dates = db.get_all_logged_dates()
            print_header("DevLog History")
            
            if not dates:
                print(f"  {Colors.YELLOW}No history yet. Start with 'devlog learn'.{Colors.ENDC}\n")
                return
            
            print(f"  {Colors.CYAN}You have logged learnings on {len(dates)} day(s):{Colors.ENDC}\n")
            for date_str in dates:
                count = len(db.get_learnings_by_date(date_str))
                print(f"  {Colors.GREEN}▸{Colors.ENDC} {date_str}  {Colors.CYAN}({count} learning{'s' if count != 1 else ''}){Colors.ENDC}")
            print(f"\n  {Colors.YELLOW}To view a specific day: devlog history YYYY-MM-DD{Colors.ENDC}\n")
    except Exception as e:
        print(f"Failed to fetch history: {e}")
        sys.exit(1)

def handle_setup(args):
    """Handles the 'setup' command."""
    import yaml
    config_dir = Path.home() / ".devlog"
    config_dir.mkdir(exist_ok=True)
    config_path = config_dir / "config.yaml"
    
    print("--- DevLog Initial Setup ---")
    
    config = {}
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
            
    # 1. GitHub
    print("\n[1] GitHub Configuration")
    curr_repo = config.get("github", {}).get("repo", "devlog-brain")
    repo = input(f"GitHub Repo Name [{curr_repo}]: ").strip() or curr_repo
    
    curr_remote = config.get("github", {}).get("remote_url", "")
    remote = input(f"GitHub Remote URL (optional) [{curr_remote}]: ").strip() or curr_remote
    
    if "github" not in config:
        config["github"] = {}
    config["github"]["repo"] = repo
    if remote:
        config["github"]["remote_url"] = remote
        
    # 2. AI Summarization
    print("\n[2] AI Summarization")
    curr_key = config.get("gemini", {}).get("api_key", "")
    key_mask = "***" + curr_key[-4:] if curr_key else ""
    key = input(f"Gemini API Key (optional) [{key_mask}]: ").strip()
    if key:
        if "gemini" not in config:
            config["gemini"] = {}
        config["gemini"]["api_key"] = key
        
    # 3. Git Repos
    print("\n[3] Git Repositories to Track")
    curr_repos = config.get("git_repos", [])
    print(f"Current repos: {', '.join(curr_repos) if curr_repos else 'None'}")
    new_repo = input("Add repository full path (leave blank to skip): ").strip()
    if new_repo:
        curr_repos.append(new_repo)
    config["git_repos"] = list(set(curr_repos))
    
    with open(config_path, 'w') as f:
        yaml.dump(config, f)
        
    print(f"\nConfiguration saved to {config_path}")
    
    # Optional Flashcard Hook Setup
    print("\n[4] Flashcard Terminal Hook")
    print("To get a random flashcard learning every time you open a terminal,")
    print("Add this to the bottom of your ~/.zshrc or ~/.bashrc:")
    print("\n  devlog quiz --auto\n")


def main():
    parser = argparse.ArgumentParser(description="DevLog: Automated Engineering Brain")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # 'learn'
    learn_parser = subparsers.add_parser("learn", help="Store a new learning")
    learn_parser.add_argument("content", type=str, help="The text of what you learned")
    learn_parser.add_argument("--tags", type=str, help="Comma-separated tags", default="")
    
    # 'today'
    today_parser = subparsers.add_parser("today", help="Preview today's entry")
    
    # 'push'
    push_parser = subparsers.add_parser("push", help="Manually trigger a GitHub push")
    
    # 'quiz'
    quiz_parser = subparsers.add_parser("quiz", help="Start a manual flashcard session")
    quiz_parser.add_argument("--auto", action="store_true", help="Run in headless hook mode")
    
    # 'search'
    search_parser = subparsers.add_parser("search", help="Full-text search across learnings")
    search_parser.add_argument("keyword", type=str, help="Keyword to search for")
    
    # 'setup'
    setup_parser = subparsers.add_parser("setup", help="Interactive first-time wizard")
    
    # 'history'
    history_parser = subparsers.add_parser("history", help="Browse past learnings by date")
    history_parser.add_argument("date", type=str, nargs="?", default=None, help="Date to view (YYYY-MM-DD). Omit to list all dates.")
    
    args = parser.parse_args()
    
    handlers = {
        "learn": handle_learn,
        "today": handle_today,
        "push": handle_push,
        "quiz": handle_quiz,
        "search": handle_search,
        "setup": handle_setup,
        "history": handle_history,
    }
    
    handler = handlers.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
