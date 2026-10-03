# AI Usage Monitor

A small KDE Plasma 6 panel widget that shows ChatGPT and Claude usage side by
side. It is based on ChatGPT Usage Monitor.

The panel shows each provider's app icon followed by a progress bar of the
remaining allowance, the percentage, and the reset time:

```text
[ChatGPT icon] ▬▬▬ 97% 10/10 10:56  |  [Claude icon] 5h ▬▬▬ 97% 19:40  wk ▬▬▬ 99% 10/08 00:00
```

Bars are green above 50% remaining, amber above 20%, and red below that,
using the Plasma theme's colours. Hover the widget to see any error details.
The icons are the installed ChatGPT (`chatgpt`) and Claude (`claude-desktop`)
app icons; a generic chat icon is used when one is not installed.

- **ChatGPT**: the remaining weekly Codex allowance on your ChatGPT
  subscription, followed by the next weekly reset in local time.
- **Claude**: the remaining allowance in the current 5-hour window and its
  reset time, then the remaining weekly allowance (all models) and its reset
  date and time, all in local time.

## How it works

### ChatGPT

The widget starts the installed Codex app server and calls its read-only
`account/rateLimits/read` method. It selects the weekly `codex` limit and
calculates `remaining percentage = 100 - usedPercent`. The Codex app server
manages the existing sign-in session; the widget never reads the token.

### Claude

The widget runs `claude -p /usage --output-format json`. In print mode
`/usage` is a local command: it sends no prompt to a model and costs nothing.
The signed-in Claude Code CLI fetches the plan limits itself, so the widget
never reads Claude credentials. The helper reads the `Current session` line
(the 5-hour window) and the `Current week (all models)` line, and calculates
`remaining percentage = 100 - used`.

## Requirements

- KDE Plasma 6 with the Plasma5Support QML module
- Python 3.9 or newer
- Codex CLI installed and signed in with ChatGPT (`codex login`)
- Claude Code CLI installed and signed in with your Claude subscription
  (`claude login`); signing in the desktop app alone is not enough

## Install

```bash
./install.sh
```

Then right-click the Plasma panel, select **Add Widgets**, search for
**AI Usage Monitor**, and add it to the panel.

The widget refreshes every five minutes.

## Check the data sources

```bash
python3 package/contents/tools/ai_usage.py --pretty
```

Each provider can also be checked on its own:

```bash
python3 package/contents/tools/chatgpt_usage.py --pretty
python3 package/contents/tools/claude_usage.py --pretty
```

The helpers print only usage fields. They never print authentication data.

## Uninstall

```bash
kpackagetool6 -t Plasma/Applet -r com.stark.ai-usage-monitor
```

## License

MIT
