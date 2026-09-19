import time
import urllib.error
import urllib.request
import boto3

REGION = "us-east-1"
SECURITY_GROUP_ID = "sg-09dc6f51fea42d278"
KEY_NAME = "demo-key"
INSTANCE_TYPE = "t3.micro"

# User-data script to set up Flask and Gunicorn on port 80
USER_DATA = """#!/bin/bash
dnf update -y
dnf install -y python3 python3-pip

# Set up app directory and virtual environment
mkdir -p /opt/app
python3 -m venv /opt/app/venv
/opt/app/venv/bin/pip install --upgrade pip
/opt/app/venv/bin/pip install flask gunicorn

# Minimal Flask app
cat << 'EOF' > /opt/app/app.py
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "Hello from AWS Deployment Agent!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
EOF

# Systemd service to run Gunicorn on port 80
cat << 'EOF' > /etc/systemd/system/flaskapp.service
[Unit]
Description=Flask Application served by Gunicorn
After=network.target

[Service]
User=root
WorkingDirectory=/opt/app
ExecStart=/opt/app/venv/bin/gunicorn -w 2 -b 0.0.0.0:80 app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable flaskapp
systemctl start flaskapp
"""


def get_amazon_linux_ami(ec2_client):
    """Find the latest Amazon Linux 2023 AMI in the region."""
    try:
        response = ec2_client.describe_images(
            Owners=["amazon"],
            Filters=[
                {"Name": "name", "Values": ["al2023-ami-2023.*-x86_64"]},
                {"Name": "state", "Values": ["available"]},
            ],
        )
        images = sorted(
            response["Images"], key=lambda x: x["CreationDate"], reverse=True
        )
        if images:
            return images[0]["ImageId"]
    except Exception as e:
        print(f"Warning: Could not dynamically query AMI: {e}")
    return "ami-0354c98ae10b02961"  # Known AL2023 AMI fallback in us-east-1


def deploy():
    ec2 = boto3.client("ec2", region_name=REGION)

    # 1. Resolve AMI and Launch exactly one EC2 instance
    ami_id = get_amazon_linux_ami(ec2)
    print(f"Launching instance with AMI: {ami_id}, InstanceType: {INSTANCE_TYPE}")

    response = ec2.run_instances(
        ImageId=ami_id,
        InstanceType=INSTANCE_TYPE,
        KeyName=KEY_NAME,
        SecurityGroupIds=[SECURITY_GROUP_ID],
        MinCount=1,
        MaxCount=1,
        UserData=USER_DATA,
    )

    # 5. Capture the returned InstanceId
    instance_id = response["Instances"][0]["InstanceId"]
    print(f"Launched instance ID: {instance_id}")

    # 6. Wait until the instance reaches running state
    print("Waiting for instance to reach running state...")
    waiter = ec2.get_waiter("instance_running")
    waiter.wait(InstanceIds=[instance_id])
    print("Instance is now running.")

    # 7. Retrieve its public IPv4 address
    desc = ec2.describe_instances(InstanceIds=[instance_id])
    instance = desc["Reservations"][0]["Instances"][0]
    public_ip = instance.get("PublicIpAddress")
    if not public_ip:
        raise RuntimeError(
            f"Instance {instance_id} does not have a public IP address assigned."
        )
    print(f"Public IPv4 Address: {public_ip}")

    deployment_url = f"http://{public_ip}"

    # 8. Make an HTTP GET request to the public IP
    # User-data takes ~30-60 seconds to execute, so poll until Gunicorn is responding.
    print(f"Connecting to {deployment_url} (waiting for user-data bootstrap to finish)...")
    max_retries = 36  # 36 * 5s = 180s
    http_status = None
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                deployment_url, headers={"User-Agent": "AWS-Deployment-Agent"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                http_status = resp.status
                if http_status == 200:
                    print(f"Server responded successfully on attempt {attempt}.")
                    break
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(5)

    # 9. Print deployment URL and HTTP status
    print("-" * 50)
    print(f"Deployment URL: {deployment_url}")
    print(f"HTTP Status: {http_status if http_status else 'No response/Timeout'}")
    print("-" * 50)


if __name__ == "__main__":
    deploy()
