#!/usr/bin/env bash
set -euo pipefail

# Carga .env si existe
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

: "${NFS_SERVER_IP:?Define NFS_SERVER_IP en .env}"
: "${NFS_MOUNT_OPTS:=rw,nfsvers=4.1}"

# Directorios locales (bind mounts ya definidos en tus compose)
mkdir -p ./uploads ./processed ./assets

# Montajes idempotentes
if ! mountpoint -q ./uploads; then
  sudo mount -t nfs -o "${NFS_MOUNT_OPTS}" "${NFS_SERVER_IP}:/exports/uploads" "$(pwd)/uploads"
fi
if ! mountpoint -q ./processed; then
  sudo mount -t nfs -o "${NFS_MOUNT_OPTS}" "${NFS_SERVER_IP}:/exports/processed" "$(pwd)/processed"
fi
if ! mountpoint -q ./assets; then
  sudo mount -t nfs -o "ro,${NFS_MOUNT_OPTS}" "${NFS_SERVER_IP}:/exports/assets" "$(pwd)/assets"
fi

echo "NFS montado sobre ./uploads ./processed ./assets"