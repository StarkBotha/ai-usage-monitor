# AI Usage Monitor

A small KDE Plasma 6 panel widget that shows the usage of your Claude
subscription. It is based on ChatGPT Usage Monitor.

The panel shows the name of the signed-in account and the Claude app icon,
followed by a progress bar of the remaining allowance, the percentage, and
the reset time:

```text
Pvt [Claude icon] 5h ▬▬▬ 97% 19:40  wk ▬▬▬ 99% 10/08 00:00
```

Bars are green above 50% remaining, amber above 20%, and red below that,
using the Plasma theme's colours. The account name is the part of the
account's email address before `@`, or a short label that you set (see
[Account labels](#account-labels-optional)). The icon is the installed Claude
(`claude-desktop`) app icon; a generic chat icon is used when it is not
installed.

The panel shows the remaining allowance in the current 5-hour window and its
reset time, then the remaining weekly allowance (all models) and its reset
date and time, all in local time.

The widget shows the account that the Claude Code CLI is signed in to. To
see the usage of a different subscription (for example personal or work),
sign in to that account in the CLI:

```bash
claude auth login
```

The widget shows the new account at the next refresh, in five minutes or
less. The Claude desktop app has its own sign-in, which does not change the
widget.

The ChatGPT meter (the remaining weekly Codex allowance) is off, but its code
stays in the package. To show it again, set `showChatgpt` to `true` in
`package/contents/ui/main.qml` and `INCLUDE_CHATGPT` to `True` in
`package/contents/tools/ai_usage.py`.

## How it works

### ChatGPT (off)

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

To name the account on the panel, the helper also runs
`claude auth status` and copies only the email address from it. It then
looks up the label for that address in the local labels file.

## Requirements

- KDE Plasma 6 with the Plasma5Support QML module
- Python 3.9 or newer
- Claude Code CLI installed and signed in with your Claude subscription
  (`claude auth login`); signing in the desktop app alone is not enough
- Only for the ChatGPT meter: Codex CLI installed and signed in with ChatGPT
  (`codex login`)

## Install

```bash
./install.sh
```

Then right-click the Plasma panel, select **Add Widgets**, search for
**AI Usage Monitor**, and add it to the panel.

The widget refreshes every five minutes.

## Account labels (optional)

By default the panel shows the part of the account's email address before
`@`, for example `jane.doe` for `jane.doe@example.com`. To show a short label
instead, for example `Pvt` or `Work`, create a labels file. The file is on
your computer only, outside the repository, so your account names are never
committed.

1. Create the configuration directory:

   ```bash
   mkdir -p ~/.config/ai-usage-monitor
   ```

2. Copy the example file into it:

   ```bash
   cp account-labels.example.json ~/.config/ai-usage-monitor/account-labels.json
   ```

3. Edit `~/.config/ai-usage-monitor/account-labels.json`. Each key is the part
   of an email address before `@`. Each value is the label for the panel:

   ```json
   {
       "jane.doe": "Pvt",
       "jdoe": "Work"
   }
   ```

The widget reads the file at each refresh, so you do not have to restart
Plasma. An account that is not in the file shows its email name. If the file
is missing or is not valid JSON, all accounts show their email names. When
`XDG_CONFIG_HOME` is set, the file is
`$XDG_CONFIG_HOME/ai-usage-monitor/account-labels.json`.

To see the label that the helper finds for the signed-in account, run:

```bash
python3 package/contents/tools/claude_usage.py --pretty
```

The `accountLabel` field shows the label.

## Check the data sources

```bash
python3 package/contents/tools/ai_usage.py --pretty
```

Each provider can also be checked on its own:

```bash
python3 package/contents/tools/claude_usage.py --pretty
python3 package/contents/tools/chatgpt_usage.py --pretty
```

The helpers print only usage fields. They never print authentication data.

## Uninstall

```bash
kpackagetool6 -t Plasma/Applet -r com.stark.ai-usage-monitor
```

## License

MIT
