#!/usr/bin/env bash
# Stop on failed commands or unset variables so installation failures stay visible.
set -euo pipefail

# Resolve the package beside this script, regardless of the caller's directory.
readonly package_id="com.stark.ai-usage-monitor"
readonly script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly package_dir="${script_dir}/package"

# Locate the user package directory to decide between install and upgrade.
readonly data_dir="${XDG_DATA_HOME:-${HOME}/.local/share}"
readonly installed_package_dir="${data_dir}/plasma/plasmoids/${package_id}"

# This package uses Plasma 6 QML APIs and must use the matching package manager.
if ! command -v kpackagetool6 >/dev/null 2>&1; then
    echo "Error: kpackagetool6 is required (KDE Plasma 6)." >&2
    exit 1
fi

# Replace an existing user installation, or install it on the first run.
# Remember whether this was an upgrade for the reload hint printed below.
is_upgrade=false
if [[ -d "${installed_package_dir}" ]]; then
    is_upgrade=true
    kpackagetool6 -t Plasma/Applet -u "${package_dir}"
else
    kpackagetool6 -t Plasma/Applet -i "${package_dir}"
fi

# Leave panel placement to the user after the package manager succeeds.
echo "Installed AI Usage Monitor."
echo "Add it with: right-click the panel > Add Widgets > AI Usage Monitor"

# A running Plasma shell keeps the previously loaded QML in memory, so an
# upgraded widget only appears after the shell restarts. Re-adding the widget
# or reinstalling the package does not clear that cache.
if [[ "${is_upgrade}" == true ]]; then
    echo "Upgraded: restart Plasma to load the new version:"
    echo "  systemctl --user restart plasma-plasmashell"
fi
