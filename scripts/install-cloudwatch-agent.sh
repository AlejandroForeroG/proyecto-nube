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

    echo "AWS credentials configured for CloudWatch Agent"
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

sudo AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}" \
     AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}" \
     AWS_SESSION_TOKEN="${AWS_SESSION_TOKEN}" \
     AWS_REGION="${AWS_REGION:-us-east-1}" \
     /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
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
    echo "✓ CloudWatch Agent is running"
else
    echo "❌ CloudWatch Agent failed to start"
    echo
    echo "Status output:"
    echo "$STATUS_OUTPUT"
    exit 1
fi

echo
echo "==> Verifying metrics collection..."
echo "Waiting 10 seconds for initial metrics..."
sleep 10

# Verificar logs del agente
if sudo grep -q "NoCredentialProviders" /opt/aws/amazon-cloudwatch-agent/logs/amazon-cloudwatch-agent.log; then
    echo "Warning: Credential errors still present in logs"
    echo "Check the last 20 lines of the log:"
    sudo tail -20 /opt/aws/amazon-cloudwatch-agent/logs/amazon-cloudwatch-agent.log
else
    echo "No credential errors in recent logs"
fi

echo
echo "=========================================="
echo "  Installation completed successfully!"
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
echo "To verify metrics are being sent, run:"
echo "  sudo tail -f /opt/aws/amazon-cloudwatch-agent/logs/amazon-cloudwatch-agent.log"
echo
