#!/bin/zsh
# Auto-launch Holmium Install Manager on ISO boot
# Press ESC within 3 seconds to skip and get a shell

echo ""
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║              HOLMIUM OS v1.0                 ║"
echo "  ║       Personal AI Operating System           ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""
echo "  Press ESC within 3 seconds to skip to shell..."
echo ""

if read -t 3 -k 1; then
    echo ""
    echo "  Skipped. Run 'holmium-install' manually."
    echo ""
else
    clear
    exec /usr/local/bin/holmium-installer
fi
