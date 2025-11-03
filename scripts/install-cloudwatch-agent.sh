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

echo
echo "==> Loading AWS credentials from .env..."
if [ -f ".env" ]; then
    export $(grep -E '^AWS_ACCESS_KEY_ID=' .env | xargs)
    export $(grep -E '^AWS_SECRET_ACCESS_KEY=' .env | xargs)
    export $(grep -E '^AWS_SESSION_TOKEN=' .env | xargs)
    export $(grep -E '^AWS_REGION=' .env | xargs)

    sudo mkdir -p /root/.aws
    sudo tee /root/.aws/credentials > /dev/null <<EOF
[AmazonCloudWatchAgent]
aws_access_key_id = ${AWS_ACCESS_KEY_ID}
aws_secret_access_key = ${AWS_SECRET_ACCESS_KEY}
aws_session_token = ${AWS_SESSION_TOKEN}
EOF

    sudo tee /root/.aws/config > /dev/null <<EOF
[profile AmazonCloudWatchAgent]
region = ${AWS_REGION:-us-east-1}
EOF

    sudo tee /opt/aws/amazon-cloudwatch-agent/etc/common-config.toml > /dev/null <<EOF
[credentials]
  shared_credential_profile = "AmazonCloudWatchAgent"
  shared_credential_file = "/root/.aws/credentials"

[proxy]

[ssl]
EOF

    sudo mkdir -p /etc/systemd/system/amazon-cloudwatch-agent.service.d
    sudo tee /etc/systemd/system/amazon-cloudwatch-agent.service.d/override.conf > /dev/null <<EOF
[Service]
Environment="AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}"
Environment="AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}"
Environment="AWS_SESSION_TOKEN=${AWS_SESSION_TOKEN}"
Environment="AWS_REGION=${AWS_REGION:-us-east-1}"
Environment="AWS_SHARED_CREDENTIALS_FILE=/root/.aws/credentials"
Environment="AWS_CONFIG_FILE=/root/.aws/config"
Environment="AWS_PROFILE=AmazonCloudWatchAgent"
EOF

    sudo systemctl daemon-reload

    echo "AWS credentials configured for CloudWatch Agent"
    echo "Note: AWS Academy credentials expire after 4 hours"
else
    echo "Warning: .env file not found"
    echo "CloudWatch Agent will use instance IAM role if available"
fi

echo
echo "==> Stopping CloudWatch Agent (if running)..."
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a stop \
    -m ec2 2>/dev/null || true

sleep 2

echo
echo "==> Starting CloudWatch Agent with credentials..."

sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a fetch-config \
    -m ec2 \
    -s \
    -c "file:$CONFIG_DEST"

echo
echo "==> Checking agent status..."
sleep 3

STATUS_OUTPUT=$(sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a status \
    -m ec2)

if echo "$STATUS_OUTPUT" | grep -q '"status".*:.*"running"'; then
    echo "CloudWatch Agent is running"
else
    echo "CloudWatch Agent failed to start"
    echo
    echo "Status output:"
    echo "$STATUS_OUTPUT"
    exit 1
fi

echo
echo "==> Verifying metrics collection..."
echo "Waiting 15 seconds for initial metrics..."
sleep 15

echo
echo "==> Checking for errors in logs..."
RECENT_ERRORS=$(sudo tail -50 /opt/aws/amazon-cloudwatch-agent/logs/amazon-cloudwatch-agent.log | grep -i "error\|credential" | tail -5)

if [ -z "$RECENT_ERRORS" ]; then
    echo "No credential errors in recent logs"
else
    echo "Recent log entries:"
    echo "$RECENT_ERRORS"
    echo
    echo "If you see credential errors, your AWS Academy session may have expired."
    echo "Update credentials in .env and re-run this script."
fi

echo
echo "=========================================="
echo "Installation completed successfully!"
echo "=========================================="
echo
echo "Metrics will be sent to:"
echo "  Namespace: ProyectoNube/EC2"
echo "  Region: ${AWS_REGION:-us-east-1}"
echo
echo "Available metrics:"
echo "  - CPU_IDLE, CPU_IOWAIT, CPU_SYSTEM, CPU_USER"
echo "  - MEM_USED (percentage)"
echo "  - DISK_USED (percentage)"
echo "  - SWAP_USED (percentage)"
echo "  - tcp_established, tcp_time_wait"
echo
echo "IMPORTANT: AWS Academy credentials expire after 3  hours"
echo "   If metrics stop being sent, update .env with new credentials"
echo "   and re-run this script: sudo bash scripts/install-cloudwatch-agent.sh"
echo
echo "Wait 2-3 minutes for metrics to appear in CloudWatch"
echo
echo "To monitor in real-time:"
echo "  sudo tail -f /opt/aws/amazon-cloudwatch-agent/logs/amazon-cloudwatch-agent.log"
echo
echo "To verify metrics are being sent (after 3 minutes):"
echo "  docker exec rest_api bash -c 'aws cloudwatch list-metrics --namespace ProyectoNube/EC2 --region us-east-1 | head -20'"
echo
