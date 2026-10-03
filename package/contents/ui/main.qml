import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as Plasma5Support
import org.kde.plasma.components as PlasmaComponents

// Own the compact panel view and the asynchronous usage refresh lifecycle.
PlasmoidItem {
    id: root

    // ChatGPT reading: remaining weekly Codex allowance and its reset time.
    // Keep the last successful reading visible while a refresh runs or fails.
    property int chatgptRemainingPercent: -1
    property double chatgptResetAt: 0
    property string chatgptError: ""

    // Claude reading: remaining 5-hour and weekly allowance with their reset times.
    // A value of -1 means no successful Claude reading yet.
    property int claudeFiveHourPercent: -1
    property double claudeFiveHourResetAt: 0
    property int claudeWeeklyPercent: -1
    property double claudeWeeklyResetAt: 0
    property string claudeError: ""

    // Shared refresh state for the single combined helper.
    property bool isLoading: false
    property string activeCommand: ""

    // Resolve the bundled helper independently of the shell working directory.
    readonly property string helperPath: decodeURIComponent(
        String(Qt.resolvedUrl("../tools/ai_usage.py")).replace("file://", "")
    )

    // Keep the label visible at panel sizes. Plasma requires a full representation
    // to instantiate a representation component instead of using direct children.
    preferredRepresentation: fullRepresentation

    // Quote the local helper path as one shell argument, including apostrophes.
    function shellQuote(value) {
        return "'" + String(value).replace(/'/g, "'\\''") + "'"
    }

    // Format local date and time components with two digits.
    function pad2(value) {
        return value < 10 ? "0" + value : String(value)
    }

    // Convert Unix seconds to a local 24-hour time; missing times use a placeholder.
    function localTime(unixSeconds) {
        if (unixSeconds <= 0) return "--:--"
        var date = new Date(unixSeconds * 1000)
        return pad2(date.getHours()) + ":" + pad2(date.getMinutes())
    }

    // Convert Unix seconds to a local date and 24-hour time.
    function localDateTime(unixSeconds) {
        if (unixSeconds <= 0) return "--/-- --:--"
        var date = new Date(unixSeconds * 1000)
        return pad2(date.getMonth() + 1) + "/" + pad2(date.getDate()) + " " + localTime(unixSeconds)
    }

    // Choose what a meter shows instead of a percentage before its first reading.
    function placeholderText(error) {
        if (isLoading) return "..."
        if (error.length > 0) return "ERR"
        return "--"
    }

    // Run at most one helper at a time; the helper owns request timeouts.
    function refresh() {
        if (isLoading) return

        isLoading = true
        activeCommand = "/usr/bin/python3 " + shellQuote(helperPath)
        commandSource.disconnectSource(activeCommand)
        commandSource.connectSource(activeCommand)
    }

    // Apply the ChatGPT section of the helper output, preserving prior readings on errors.
    function applyChatgpt(section) {
        if (!section || !section.ok) {
            chatgptError = (section && section.error) || "Could not retrieve ChatGPT usage"
            return
        }
        chatgptRemainingPercent = Number(section.remainingPercent)
        chatgptResetAt = Number(section.resetAt || 0)
        chatgptError = ""
    }

    // Apply the Claude section of the helper output, preserving prior readings on errors.
    function applyClaude(section) {
        if (!section || !section.ok) {
            claudeError = (section && section.error) || "Could not read Claude usage"
            return
        }
        var fiveHour = section.fiveHour || {}
        var weekly = section.weekly || {}
        claudeFiveHourResetAt = Number(fiveHour.resetAt || 0)
        claudeWeeklyResetAt = Number(weekly.resetAt || 0)
        claudeWeeklyPercent = Number(weekly.remainingPercent)
        claudeError = ""

        claudeFiveHourPercent = Number(fiveHour.remainingPercent)
    }

    // Accept the combined helper JSON contract; each provider is applied independently.
    function applyOutput(output) {
        try {
            var payload = JSON.parse(output)
            applyChatgpt(payload.chatgpt)
            applyClaude(payload.claude)
        } catch (error) {
            chatgptError = "Invalid helper response"
            claudeError = "Invalid helper response"
        }
    }

    // Plasma 6 exposes the executable engine through its compatibility module.
    // Only the fixed Python command and quoted bundled path reach the shell.
    Plasma5Support.DataSource {
        id: commandSource
        engine: "executable"
        connectedSources: []

        // Disconnect completed commands and ignore results from unrelated sources.
        onNewData: function(sourceName, data) {
            disconnectSource(sourceName)
            if (sourceName !== root.activeCommand) return

            root.isLoading = false
            var output = String(data["stdout"] || "").trim()
            if (output.length === 0) {
                root.chatgptError = "No response from usage helper"
                root.claudeError = "No response from usage helper"
                return
            }
            root.applyOutput(output)
        }
    }

    // Poll every five minutes without requiring user interaction.
    Timer {
        interval: 300000
        repeat: true
        running: true
        onTriggered: root.refresh()
    }

    // Populate the label as soon as Plasma creates the applet.
    Component.onCompleted: refresh()

    // Show each provider as its app icon followed by its usage meters. Errors
    // are listed in the tooltip because the panel only has room for "ERR".
    toolTipMainText: "AI Usage"
    toolTipSubText: [chatgptError.length > 0 ? "ChatGPT: " + chatgptError : "",
                     claudeError.length > 0 ? "Claude: " + claudeError : ""]
        .filter(function(line) { return line.length > 0 }).join("\n")

    fullRepresentation: RowLayout {
        id: panelRow
        spacing: Kirigami.Units.smallSpacing

        // Size icons to the panel's text line so they match the labels.
        readonly property int iconSize: Kirigami.Units.iconSizes.smallMedium

        Layout.minimumWidth: implicitWidth
        Layout.minimumHeight: implicitHeight

        // Use the installed ChatGPT app icon, falling back to a generic chat icon.
        Kirigami.Icon {
            source: "chatgpt"
            fallback: "dialog-messages"
            Layout.preferredWidth: panelRow.iconSize
            Layout.preferredHeight: panelRow.iconSize
        }

        UsageMeter {
            percent: root.chatgptRemainingPercent
            placeholder: root.placeholderText(root.chatgptError)
            resetText: root.chatgptResetAt > 0 ? root.localDateTime(root.chatgptResetAt) : ""
        }

        // Separate the two providers with a faint vertical rule.
        Rectangle {
            Layout.preferredWidth: 1
            Layout.preferredHeight: panelRow.iconSize
            Layout.leftMargin: Kirigami.Units.smallSpacing
            Layout.rightMargin: Kirigami.Units.smallSpacing
            color: Kirigami.Theme.textColor
            opacity: 0.3
        }

        // Use the installed Claude desktop icon, falling back to a generic chat icon.
        Kirigami.Icon {
            source: "claude-desktop"
            fallback: "dialog-messages"
            Layout.preferredWidth: panelRow.iconSize
            Layout.preferredHeight: panelRow.iconSize
        }

        UsageMeter {
            label: "5h"
            percent: root.claudeFiveHourPercent
            placeholder: root.placeholderText(root.claudeError)
            resetText: root.claudeFiveHourResetAt > 0 ? root.localTime(root.claudeFiveHourResetAt) : ""
        }

        UsageMeter {
            label: "wk"
            percent: root.claudeWeeklyPercent
            placeholder: root.placeholderText(root.claudeError)
            resetText: root.claudeWeeklyResetAt > 0 ? root.localDateTime(root.claudeWeeklyResetAt) : ""
            Layout.leftMargin: Kirigami.Units.smallSpacing
        }
    }
}
