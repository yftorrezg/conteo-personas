#!/usr/bin/env bash
# Escribe Raspberry Pi OS en la SD y la deja lista (usuario, SSH, WiFi, proyecto, auto-instalación).
# Uso:  sudo bash pi/flash_sd.sh          (DEV=/dev/mmcblk0 por defecto)
set -euo pipefail
[ "$EUID" -eq 0 ] || { echo "Ejecuta con sudo"; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(dirname "$HERE")
source "$HERE/wifi.env"
DEV=${DEV:-/dev/mmcblk0}
IMG=$(ls "$ROOT"/os-image/*.img.xz | head -1)

for v in PI_PASS WIFI_SSID WIFI_PASS; do
  [ "${!v}" = "CAMBIAR" ] && { echo "Edita pi/wifi.env: falta $v"; exit 1; }
done
[ -b "$DEV" ] || { echo "No existe $DEV"; exit 1; }
SIZE=$(lsblk -bdno SIZE "$DEV")
if [ "$SIZE" -lt 25000000000 ] || [ "$SIZE" -gt 34000000000 ]; then
  echo "ABORTO: $DEV mide $SIZE bytes; no parece la SD de 32 GB."; exit 1
fi
if lsblk -no MOUNTPOINTS "$DEV" | grep -Eq '^(/|/boot|/home)$'; then
  echo "ABORTO: $DEV contiene el sistema de esta PC."; exit 1
fi
echo "=== Se BORRARÁ por completo: ==="; lsblk -o NAME,SIZE,MODEL,FSTYPE,LABEL "$DEV"
echo "Imagen: $IMG"; sleep 5

for p in $(lsblk -lnpo NAME "$DEV" | tail -n +2); do umount "$p" 2>/dev/null || true; done
echo "=== Escribiendo imagen (3-6 min) ==="
xz -dc "$IMG" | dd of="$DEV" bs=4M conv=fsync status=progress
sync; partprobe "$DEV" || true; sleep 3; udevadm settle || true
for p in $(lsblk -lnpo NAME "$DEV" | tail -n +2); do umount "$p" 2>/dev/null || true; done
if [[ "$DEV" =~ [0-9]$ ]]; then P="${DEV}p"; else P="$DEV"; fi

MNT=$(mktemp -d)
mount "${P}1" "$MNT"
echo "=== Configurando primer arranque ==="
export PI_USER PI_PASS PI_HOST WIFI_COUNTRY WIFI_SSID WIFI_PASS WIFI2_SSID WIFI2_PASS WIFI3_SSID WIFI3_PASS MNT
export PASS_HASH=$(openssl passwd -6 "$PI_PASS")
python3 - <<'PY'
import json, os
e = os.environ
q = json.dumps
mnt = e["MNT"]
aps = f'        {q(e["WIFI_SSID"])}:\n          password: {q(e["WIFI_PASS"])}\n'
for n in ("WIFI2", "WIFI3"):
    if e.get(n + "_SSID"):
        aps += f'        {q(e[n + "_SSID"])}:\n          password: {q(e.get(n + "_PASS", ""))}\n'
open(f"{mnt}/network-config", "w").write(f"""network:
  version: 2
  ethernets:
    eth0:
      dhcp4: true
      optional: true
  wifis:
    wlan0:
      dhcp4: true
      optional: false
      regulatory-domain: {q(e["WIFI_COUNTRY"])}
      access-points:
{aps}""")
u = e["PI_USER"]
open(f"{mnt}/user-data", "w").write(f"""#cloud-config
hostname: {e["PI_HOST"]}
manage_etc_hosts: true
enable_ssh: true
ssh_pwauth: true
users:
- name: {u}
  groups: users,adm,dialout,audio,netdev,video,plugdev,cdrom,games,input,gpio,spi,i2c,render,sudo
  shell: /bin/bash
  lock_passwd: false
  passwd: {e["PASS_HASH"]}
  sudo: ALL=(ALL) NOPASSWD:ALL
runcmd:
- [ bash, -c, "mkdir -p /home/{u} && cp -r /boot/firmware/conteo /home/{u}/conteo && chown -R {u}:{u} /home/{u}/conteo" ]
- [ bash, -c, "su - {u} -c 'bash /home/{u}/conteo/pi/setup_pi.sh' > /home/{u}/setup.log 2>&1; echo FIN >> /home/{u}/setup.log" ]
""")
PY
echo "=== Copiando proyecto a la SD ==="
mkdir -p "$MNT/conteo"
cp -r "$ROOT/src" "$ROOT/pi" "$ROOT/tests" "$ROOT/requirements.txt" "$MNT/conteo/"
rm -rf "$MNT/conteo/src/__pycache__" "$MNT/conteo/pi/wifi.env"
sync; umount "$MNT"; rmdir "$MNT"
echo
echo "LISTO. Puedes retirar la SD con seguridad y ponerla en la Raspberry."
