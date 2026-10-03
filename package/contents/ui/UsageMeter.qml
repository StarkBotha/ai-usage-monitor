import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PlasmaComponents

// One usage reading in the panel: optional window label, a progress bar of
// the remaining allowance, the percentage, and the reset time.
RowLayout {
    id: meter

    // Short window name shown before the bar, for example "5h"; empty hides it.
    property string label: ""

    // Remaining allowance from 0 to 100, or -1 when no reading exists yet.
    property int percent: -1

    // Text shown in place of the percentage when no reading exists ("...", "ERR").
    property string placeholder: "--"

    // Already formatted reset time; empty hides it.
    property string resetText: ""

    spacing: Kirigami.Units.smallSpacing

    // Pick the bar colour from the theme so it follows light and dark schemes:
    // plenty left is positive, getting low is neutral (amber), nearly gone is negative.
    readonly property color fillColor: percent > 50 ? Kirigami.Theme.positiveTextColor
        : percent > 20 ? Kirigami.Theme.neutralTextColor
        : Kirigami.Theme.negativeTextColor

    PlasmaComponents.Label {
        visible: meter.label.length > 0
        text: meter.label
        opacity: 0.7
    }

    // Draw the bar directly so its size stays compact and predictable in a panel.
    Rectangle {
        id: track
        Layout.preferredWidth: Kirigami.Units.gridUnit * 3
        Layout.preferredHeight: Math.max(4, Math.round(Kirigami.Units.smallSpacing * 1.5))
        Layout.alignment: Qt.AlignVCenter
        radius: height / 2
        color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                       Kirigami.Theme.textColor.b, 0.2)

        // The fill width is the remaining share; unknown readings leave the track empty.
        Rectangle {
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: meter.percent > 0 ? Math.max(height, track.width * meter.percent / 100) : 0
            radius: parent.radius
            color: meter.fillColor
        }
    }

    PlasmaComponents.Label {
        text: meter.percent >= 0 ? meter.percent + "%" : meter.placeholder
        font.bold: true
    }

    PlasmaComponents.Label {
        visible: meter.resetText.length > 0
        text: meter.resetText
        opacity: 0.7
    }
}
