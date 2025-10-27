#!/usr/bin/env bash
set -euo pipefail
for d in assets processed uploads; do
  if mountpoint -q "./$d"; then
    sudo umount "./$d"
  fi
done
echo "NFS desmontado de ./uploads ./processed ./assets"