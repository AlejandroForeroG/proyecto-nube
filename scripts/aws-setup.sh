#!/usr/bin/env bash
# Prepara un entorno de desarrollo: Python, Docker(+Compose), Git(+gh), Node con nvm.
# Clona el proyecto 'proyecto-nube' y configura Docker correctamente.
# Probado en Ubuntu 20.04/22.04/24.04

set -euo pipefail

# ---------- Helpers ----------
need_sudo() {
  if [ "$EUID" -ne 0 ]; then
    echo ">> Using sudo for privileged operations."
    SUDO="sudo"
  else
    SUDO=""
  fi
}
pkg_installed() {
  dpkg -s "$1" &>/dev/null
}
append_once() {
  local line="$1" file="$2"
  grep -qxF "$line" "$file" 2>/dev/null || echo "$line" >> "$file"
}

usage() {
  cat <<EOF
Usage: $0 --nfs-role <client|server|none>

Opciones:
  --nfs-role client   Ejecuta nfs-client-mount.sh al final (para instancias app/worker)
  --nfs-role server   Ejecuta nfs-server-mount.sh al final (para instancia file-server)
  --nfs-role none     No configura NFS (para desarrollo local)

Ejemplo:
  sudo ./scripts/aws-setup.sh --nfs-role client
  sudo ./scripts/aws-setup.sh --nfs-role server
EOF
  exit 1
}

# ---------- Parse args ----------
NFS_ROLE=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --nfs-role)
      NFS_ROLE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "Error: argumento desconocido '$1'" >&2
      usage
      ;;
  esac
done

if [ -z "$NFS_ROLE" ]; then
  echo "Error: --nfs-role es obligatorio" >&2
  usage
fi

if [[ ! "$NFS_ROLE" =~ ^(client|server|none)$ ]]; then
  echo "Error: --nfs-role debe ser 'client', 'server' o 'none'" >&2
  usage
fi

need_sudo

echo ">> Updating apt index…"
$SUDO apt-get update -y

echo ">> Installing base utilities…"
$SUDO apt-get install -y --no-install-recommends \
  ca-certificates curl gnupg lsb-release apt-transport-https \
  software-properties-common build-essential unzip git

echo "==> Installing Python toolchain…"
$SUDO apt-get install -y python3 python3-venv python3-pip
if ! pkg_installed pipx; then
  $SUDO apt-get install -y pipx || true
  $SUDO -u "${SUDO_USER:-$USER}" pipx ensurepath || true
fi

python3 --version || true
pip3 --version || true

echo "==> Installing Docker Engine + Compose v2…"

$SUDO apt-get remove -y docker docker-engine docker.io containerd runc || true

if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
  $SUDO install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | $SUDO gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  $SUDO chmod a+r /etc/apt/keyrings/docker.gpg
fi

ARCH=$(dpkg --print-architecture)
UBUNTU_CODENAME=$(. /etc/os-release && echo "$VERSION_CODENAME")
if [ ! -f /etc/apt/sources.list.d/docker.list ]; then
  echo \
"deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME} stable" | \
  $SUDO tee /etc/apt/sources.list.d/docker.list >/dev/null
fi

$SUDO apt-get update -y
$SUDO apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

$SUDO systemctl enable docker
$SUDO systemctl start docker

if ! id -nG "${SUDO_USER:-$USER}" | grep -qw docker; then
  echo ">> Adding ${SUDO_USER:-$USER} to docker group…"
  $SUDO usermod -aG docker "${SUDO_USER:-$USER}"
fi

docker --version || true
docker compose version || true

echo "==> Installing GitHub CLI…"
if ! command -v gh &>/dev/null; then
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | \
    $SUDO dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
  $SUDO chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | \
    $SUDO tee /etc/apt/sources.list.d/github-cli.list >/dev/null
  $SUDO apt-get update -y
  $SUDO apt-get install -y gh
fi

git --version || true
gh --version || true

echo "==> Installing nvm and Node.js LTS…"

USER_HOME=$(getent passwd "${SUDO_USER:-$USER}" | cut -d: -f6)
SHELL_NAME=$(basename "${SHELL:-bash}")
RC_FILE="$USER_HOME/.${SHELL_NAME}rc"
[ "$SHELL_NAME" = "zsh" ] && RC_FILE="$USER_HOME/.zshrc"
[ "$SHELL_NAME" = "bash" ] && RC_FILE="$USER_HOME/.bashrc"

if [ ! -d "$USER_HOME/.nvm" ]; then
  echo ">> Installing nvm for ${SUDO_USER:-$USER}…"
  $SUDO -u "${SUDO_USER:-$USER}" bash -lc \
    'curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash'
fi

append_once 'export NVM_DIR="$HOME/.nvm"' "$RC_FILE"
append_once '[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"' "$RC_FILE"
append_once '[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"' "$RC_FILE"

$SUDO -u "${SUDO_USER:-$USER}" bash -lc \
  'export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; nvm install --lts; nvm alias default "lts/*"; node -v; npm -v'

echo "==> Cloning project 'proyecto-nube'…"

PROJECT_DIR="$USER_HOME/proyecto-nube"
if [ -d "$PROJECT_DIR/.git" ]; then
  echo ">> Existing repo found, pulling latest changes..."
  $SUDO -u "${SUDO_USER:-$USER}" git -C "$PROJECT_DIR" pull || true
else
  echo ">> Cloning fresh repo..."
  $SUDO -u "${SUDO_USER:-$USER}" git clone https://github.com/AlejandroForeroG/proyecto-nube.git "$PROJECT_DIR" || {
    echo ">> Clone failed, creating directory manually..."
    $SUDO -u "${SUDO_USER:-$USER}" mkdir -p "$PROJECT_DIR"
  }
fi

echo "==> Fixing Docker socket permissions..."
$SUDO chown root:docker /var/run/docker.sock || true
$SUDO chmod 660 /var/run/docker.sock || true

echo
echo "===================== SUMMARY ====================="
echo "Python:      $(python3 --version 2>/dev/null || echo 'not found')"
echo "Docker:      $(docker --version 2>/dev/null || echo 'not found')"
echo "Compose:     $(docker compose version 2>/dev/null || echo 'not found')"
echo "Git:         $(git --version 2>/dev/null || echo 'not found')"
echo "Node:        $($SUDO -u "${SUDO_USER:-$USER}" bash -lc 'node -v' 2>/dev/null || echo 'reload shell')"
echo "NFS Role:    $NFS_ROLE"
echo "==================================================="

# ---------- NFS Setup ----------
echo
echo "==> Configuring NFS (role: $NFS_ROLE)..."

cd "$PROJECT_DIR"

case "$NFS_ROLE" in
  client)
    if [ -f "scripts/nfs-client-mount.sh" ]; then
      echo ">> Running NFS client mount script..."
      chmod +x scripts/nfs-client-mount.sh
      $SUDO ./scripts/nfs-client-mount.sh
      echo ">> NFS client configured. Mounts:"
      mountpoint ./uploads && echo "  ✓ ./uploads"
      mountpoint ./processed && echo "  ✓ ./processed"
      mountpoint ./assets && echo "  ✓ ./assets"
    else
      echo "Warning: scripts/nfs-client-mount.sh not found" >&2
    fi
    ;;
  server)
    if [ -f "scripts/nfs-server-mount.sh" ]; then
      echo ">> Running NFS server bootstrap script..."
      chmod +x scripts/nfs-server-mount.sh
      $SUDO ./scripts/nfs-server-mount.sh
      echo ">> NFS server directories ready at /srv/nfs"
      echo ">> Now start the NFS container with:"
      echo "   cd $PROJECT_DIR/docker && docker compose -f compose.file-server.yml up -d"
    else
      echo "Warning: scripts/nfs-server-mount.sh not found" >&2
    fi
    ;;
  none)
    echo ">> Skipping NFS configuration (role: none)"
    ;;
esac

echo
echo ">> Setup complete!"
echo ">> Please log out and back in (or reboot) to apply docker group permissions."