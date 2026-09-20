```markdown
# AWS Deployment Agent

An agentic tool that automates Flask app deployment 
to AWS EC2 — so beginners don't have to.

## The Problem
Deploying to AWS as a beginner means dealing with:
- IAM, Security Groups, EC2, AMIs all at once
- Vague errors ("Failed to connect")
- SSH setup complexity
- Public IP changes
- Security Group rule confusion

## The Solution
Type a request. Click Deploy. Get a live URL.

The agent handles:
- Security Group creation
- EC2 instance launch (t3.micro, Amazon Linux)
- Flask + Gunicorn + systemd bootstrap via user-data
- Waits for instance to be ready
- Verifies HTTP response
- Returns working URL

## Demo
https://youtu.be/AR-muykbXhA?si=CvUvDbQrLRhiAIcQ

## Architecture
```
User (Web UI)
    ↓
Flask API (app.py)
    ↓
Deployment Agent (agent.py)
    ↓
boto3 → AWS EC2 API
    ↓
t3.micro EC2 Instance
    ↓
Amazon Linux + Flask + Gunicorn + systemd
    ↓
🌐 Live URL
```

## Stack
- Python, boto3
- AWS EC2, IAM, Security Groups
- Amazon Linux 2023
- Flask, Gunicorn, systemd
- Vanilla HTML/CSS/JS frontend

## How to Run
```bash
git clone https://github.com/Mufeed06-cmd/aws-deployment-agent
cd aws-deployment-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open http://localhost:5000 → Click Deploy

## Built By
Shaik Nakeeb Mufeed 
GitHub: Mufeed06-cmd

