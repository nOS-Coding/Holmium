#!/usr/bin/env bash
# shellcheck disable=SC2034
iso_name="holmium-os-amd"
iso_label="HOLMIUM_AMD_$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y%m)"
iso_publisher="Holmium OS <https://holmium.ai>"
iso_application="Holmium OS Installer — AMD"
iso_version="$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y.%m.%d)"
install_dir="holmium"
buildmodes=('iso')
bootmodes=('bios.syslinux' 'uefi.grub')
arch="x86_64"
pacman_conf="pacman.conf"
airootfs_image_type="erofs"
airootfs_image_tool_options=('-zlzma,109' -E 'ztailpacking')
bootstrap_tarball_compression=(xz -9e)
file_permissions=(
  ["/etc/shadow"]="0:0:400"
  ["/root/.zlogin"]="0:0:755"
  ["/usr/local/bin/holmium-installer"]="0:0:755"
)
