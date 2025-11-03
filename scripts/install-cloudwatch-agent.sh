set -euo pipefail

echo "=========================================="
echo "CloudWatch Agent Installation Script"
echo "=========================================="
echo

if [ ! -f "app/cloudwatch/cloudwatch-agent-config.json" ]; then
    echo "Error: cloudwatch-agent-config.json not found"
    echo "Run this script from the project root directory"
    exit 1
fi

# Instalar el agente
echo "==> Installing CloudWatch Agent..."
if ! command -v amazon-cloudwatch-agent-ctl &> /dev/null; then
    wget -q https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
    sudo dpkg -i -E ./amazon-cloudwatch-agent.deb
    rm -f ./amazon-cloudwatch-agent.deb
    echo "CloudWatch Agent installed"
else
    echo "CloudWatch Agent already installed"
fi

echo
echo "==> Configuring CloudWatch Agent..."
CONFIG_SOURCE="./app/cloudwatch/cloudwatch-agent-config.json"
CONFIG_DEST="/opt/aws/amazon-cloudwatch-agent/etc/cloudwatch-agent-config.json"

sudo cp "$CONFIG_SOURCE" "$CONFIG_DEST"
echo "Configuration file copied to $CONFIG_DEST"

# Verificar credenciales AWS
echo
echo "==> Verifying AWS credentials..."
if aws sts get-caller-identity &> /dev/null; then
    echo "AWS credentials are valid"
else
    echo "AWS credentials not configured or expired"
    echo "Make sure your .env has valid AWS credentials"
    exit 1
fi

echo
echo "==> Starting CloudWatch Agent..."
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a fetch-config \
    -m ec2 \
    -s \
    -c "file:$CONFIG_DEST"

echo
echo "==> Checking agent status..."
sleep 3

STATUS_OUTPUT=$(sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a query \
    -m ec2 \
    -c default)

if echo "$STATUS_OUTPUT" | grep -q '"status":"running"'; then
    echo "CloudWatch Agent is running"
else
    echo "CloudWatch Agent failed to start"
    echo
    echo "Status output:"
    echo "$STATUS_OUTPUT"
    exit 1
fi

echo
echo "=========================================="
echo "Installation completed successfully!"
echo "=========================================="
echo
echo "Metrics will be sent to:"
echo "  Namespace: ProyectoNube/EC2"
echo "  Region: us-east-1"
echo
echo "Available metrics:"
echo "  - CPU_IDLE, CPU_IOWAIT, CPU_SYSTEM, CPU_USER"
echo "  - MEM_USED (percentage)"
echo "  - DISK_USED (percentage)"
echo "  - SWAP_USED (percentage)"
echo "  - tcp_established, tcp_time_wait"
echo
echo "Wait 2-3 minutes for metrics to appear in CloudWatch"
echo
