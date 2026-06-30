# os — Arch Linux Base + OpenRC Services

Arch Linux minimal base with OpenRC init. Contains base config, OpenRC service definitions, archiso custom profile for installer ISO.

- `packages.txt` — list of Arch packages for a minimal Holmium system
- `setup.sh` — bootstrap script that installs and configures everything on a fresh Arch minimal install
- `services/` — OpenRC service scripts for each Holmium component
- `kernel/` — custom `linux-holmium` kernel PKGBUILD + patches
