import json
import urllib.request
from datetime import datetime

from src import db, env

# Commands that carry zero learning signal — never send these to the model.
_NOISE_COMMANDS = {
    "ls", "ll", "la", "l", "cd", "pwd", "clear", "cls", "exit", "history",
    "cat", "echo", "man", "whoami", "date", "which", "type", "alias",
    "git status", "git log", "git diff", "git branch", "git fetch",
    "kubectl get pods", "kubectl get nodes", "kubectl get svc",
    "docker ps", "docker images", "top", "htop", "ps", "df", "du",
}

def _get_gemini_api_key() -> str:
    """Priority: os.environ → .env.local → ~/.devlog/config.yaml"""
    key = env.get("GEMINI_API_KEY")
    if key:
        return key
    try:
        from src.collector import get_config
        config = get_config()
        return config.get("gemini", {}).get("api_key", "")
    except Exception:
        return ""

def _filter_commands(commands: list[str]) -> list[str]:
    """
    Strip navigation noise and keep only commands that reveal intent.
    A command is noise if it matches a known no-op or has fewer than 2 tokens
    with no flags/arguments (e.g. bare `ls` vs `ls -la /etc/nginx`).
    """
    filtered = []
    for cmd in commands:
        base = cmd.strip().split()[0] if cmd.strip() else ""
        full_base = " ".join(cmd.strip().split()[:2])

        is_bare_noise = cmd.strip() in _NOISE_COMMANDS
        is_base_noise = base in _NOISE_COMMANDS and len(cmd.split()) < 3
        is_full_noise = full_base in _NOISE_COMMANDS

        if not (is_bare_noise or is_base_noise or is_full_noise):
            filtered.append(cmd.strip())

    # Cap at 80 most recent meaningful commands to stay within token budget
    return filtered[-80:]


# ---------------------------------------------------------------------------
# Prompt engineering
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a technical journal engine for a Cloud and DevOps engineer.
Your only job is to convert a day's raw terminal activity into a structured, \
honest engineering log — the kind a senior engineer would write for themselves, \
not for a manager.

Rules you must follow without exception:
- Write for an engineer who ran these commands. They already know what `kubectl`, \
`terraform`, and `aws` are. Never explain basics.
- Every insight must be grounded in a specific command from the input. \
No hallucinated observations.
- If a section has nothing meaningful to say, omit it entirely. \
Do not write filler like "No anti-patterns detected."
- Do not use emojis anywhere in the output.
- Do not use bold text for decoration. Bold only the thing being defined or called out.
- Output clean GitHub-flavored Markdown only. No preamble, no sign-off.\
"""

_USER_PROMPT_TEMPLATE = """\
Today: {date}

## Commands run today (noise already filtered)
```
{commands}
```

## Learnings I explicitly recorded today
{learnings}

---

Using the commands and learnings above, produce a DevLog entry in exactly this structure.
Only include a section if you have real, grounded content for it.

---

# {date}

## What I worked on
<!-- 2–4 sentences. Infer the actual work narrative from command clusters.
     Group related commands into a coherent story. Be specific — name the services,
     flags, and resources that appear in the commands. -->

## Key commands worth keeping
<!-- A table of commands that are non-obvious, flag-heavy, or situationally specific.
     Ignore anything a junior engineer would know cold. -->

| Command | Why it matters |
|---------|---------------|
| `command here` | one-line explanation of what this specific invocation does |

## Learnings
<!-- Start with any manually recorded learnings (they are highest signal).
     Then extract implicit learnings from the commands: a flag used correctly,
     a pattern that reveals understanding, a resource type that has nuance.
     Write each learning as a tight declarative fact. No padding. -->

- **concept or tool**: the precise thing learned, written as a reusable rule

## Friction & anti-patterns
<!-- Only include if you spot something concrete: a retry loop in the commands,
     a permission error worked around the wrong way, a force flag that suggests
     something went wrong, repeated failed attempts before success.
     Be specific — quote the actual command that raised the flag. -->

- `the command` — what the pattern suggests and the better approach

## Open threads
<!-- Infer from context: a command that suggests an ongoing investigation,
     an incomplete deploy, a resource created but never verified, a flag
     that indicates something was left in a temporary state.
     Only include if there is clear evidence in the commands. -->

- one line per thread, concrete and specific

---

Return only the markdown. Start directly with the `# {date}` heading.\
"""

def generate_daily_summary(commands: list[str], manual_learnings: list[str]) -> str:
    api_key = _get_gemini_api_key()
    if not api_key:
        return _generate_fallback_summary(commands, manual_learnings)

    meaningful_commands = _filter_commands(commands)

    if not meaningful_commands and not manual_learnings:
        return _generate_fallback_summary(commands, manual_learnings)

    today_str = datetime.now().strftime("%B %d, %Y")

    learnings_block = (
        "\n".join(f"- {l}" for l in manual_learnings)
        if manual_learnings
        else "_None recorded today._"
    )
    commands_block = "\n".join(meaningful_commands) if meaningful_commands else "_None._"

    user_prompt = _USER_PROMPT_TEMPLATE.format(
        date=today_str,
        commands=commands_block,
        learnings=learnings_block,
    )

    payload = {
        "system_instruction": {
            "parts": [{"text": _SYSTEM_PROMPT}]
        },
        "contents": [{
            "parts": [{"text": user_prompt}]
        }],
        "generationConfig": {
            "temperature": 0.3,       # Low — we want factual extraction, not creative writing
            "topP": 0.85,
            "maxOutputTokens": 1200,  # Enough for a full day log, not a novel
        }
    }

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/gemini-2.5-flash:generateContent?key={api_key}"
    )
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"[devlog] Gemini unavailable: {e}. Falling back to static summary.")
        return _generate_fallback_summary(commands, manual_learnings)


def _generate_fallback_summary(commands: list[str], manual_learnings: list[str]) -> str:
    """
    Static fallback: clean and readable, no AI required.
    Used when Gemini is disabled, rate-limited, or unreachable.
    """
    today_str = datetime.now().strftime("%B %d, %Y")
    meaningful = _filter_commands(commands)

    lines = [f"# {today_str}", ""]

    if manual_learnings:
        lines += ["## Learnings", ""]
        for l in manual_learnings:
            lines.append(f"- {l}")
        lines.append("")

    if meaningful:
        lines += ["## Commands", ""]
        lines.append("```")
        lines += meaningful[:60]
        if len(meaningful) > 60:
            lines.append(f"# ... and {len(meaningful) - 60} more")
        lines.append("```")
        lines.append("")

    if not manual_learnings and not meaningful:
        lines.append("_Nothing recorded today._")

    return "\n".join(lines)