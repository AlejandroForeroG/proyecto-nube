#!/usr/bin/env bash
set -euo pipefail

if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

: "${NFS_SERVER_IP:?Define NFS_SERVER_IP en .env}"
: "${NFS_MOUNT_OPTS:=rw,vers=4.1,rsize=1048576,wsize=1048576,noatime,hard,timeo=600,retrans=2}"

if ! command -v mount.nfs >/dev/null 2>&1 && [ ! -x /sbin/mount.nfs ] && [ ! -x /usr/sbin/mount.nfs ]; then
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -y
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nfs-common
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y nfs-utils
  elif command -v yum >/dev/null 2>&1; then
    sudo yum install -y nfs-utils
  else
    echo "No se pudo instalar cliente NFS. Hazlo manualmente." >&2
    exit 1
  fi
fi

echo "Esperando NFS ${NFS_SERVER_IP}:2049..."
for i in $(seq 1 30); do
  if timeout 2 bash -c "exec 3<>/dev/tcp/${NFS_SERVER_IP}/2049" 2>/dev/null; then
    break
  fi
  sleep 1
  if [ "$i" = "30" ]; then
    echo "Timeout esperando NFS en ${NFS_SERVER_IP}:2049" >&2
    exit 1
  fi
done

mkdir -p ./uploads ./processed ./assets

BOOTSTRAP="/mnt/nfs-bootstrap-$$"
sudo mkdir -p "${BOOTSTRAP}"

cleanup() {
  set +e
  if mountpoint -q "${BOOTSTRAP}" 2>/dev/null; then
    sudo umount "${BOOTSTRAP}" 2>/dev/null || true
  fi
  sudo rmdir "${BOOTSTRAP}" 2>/dev/null || true
}
trap cleanup EXIT

sudo mount -t nfs -o "${NFS_MOUNT_OPTS}" "${NFS_SERVER_IP}:/" "${BOOTSTRAP}"

for d in uploads processed assets; do
  if [ ! -d "${BOOTSTRAP}/${d}" ]; then
    sudo mkdir -p "${BOOTSTRAP}/${d}"
    sudo chmod 0777 "${BOOTSTRAP}/${d}"
  fi
done

sudo umount "${BOOTSTRAP}"
sudo rmdir "${BOOTSTRAP}"
trap - EXIT

if ! mountpoint -q ./uploads; then
  sudo mount -t nfs -o "${NFS_MOUNT_OPTS}" "${NFS_SERVER_IP}:/uploads" "$(pwd)/uploads"
fi
if ! mountpoint -q ./processed; then
  sudo mount -t nfs -o "${NFS_MOUNT_OPTS}" "${NFS_SERVER_IP}:/processed" "$(pwd)/processed"
fi
if ! mountpoint -q ./assets; then
  sudo mount -t nfs -o "ro,${NFS_MOUNT_OPTS}" "${NFS_SERVER_IP}:/assets" "$(pwd)/assets"
fi

echo "NFS montado: ./uploads, ./processed, ./assets (server: ${NFS_SERVER_IP})"