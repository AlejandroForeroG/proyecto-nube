#!/usr/bin/env bash
set -euo pipefail
sudo mkdir -p /srv/nfs/uploads /srv/nfs/processed /srv/nfs/assets
sudo chown -R nobody:nogroup /srv/nfs
sudo chmod -R 0777 /srv/nfs
echo "NFS host dirs ready in /srv/nfs"