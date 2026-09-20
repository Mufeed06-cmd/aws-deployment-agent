import sys
import threading
from flask import Flask, jsonify, render_template

import agent

app = Flask(__name__)

# Shared deployment state
deployment_state = {
    "status": "idle",  # "idle" | "running" | "success" | "failed"
    "logs": [],
    "url": None,
    "error": None,
}
state_lock = threading.Lock()


class StreamInterceptor:
    """Intercepts sys.stdout to monitor deployment progress in real time."""

    def __init__(self, original_stdout, on_line):
        self.original_stdout = original_stdout
        self.on_line = on_line
        self._buffer = ""

    def write(self, text):
        if self.original_stdout:
            self.original_stdout.write(text)
            self.original_stdout.flush()
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self.on_line(line.strip())

    def flush(self):
        if self.original_stdout:
            self.original_stdout.flush()


def _handle_agent_output(line):
    """Parses agent stdout and appends milestone logs."""
    if not line:
        return
    with state_lock:
        if "Launching instance with AMI" in line:
            msg = "⚙️ Launching EC2 instance..."
            if msg not in deployment_state["logs"]:
                deployment_state["logs"].append(msg)
        elif "Connecting to" in line and "bootstrap" in line:
            msg = "⏳ Waiting for bootstrap..."
            if msg not in deployment_state["logs"]:
                deployment_state["logs"].append(msg)
        elif "Public IPv4 Address:" in line:
            ip = line.split("Public IPv4 Address:")[1].strip()
            if not deployment_state["url"]:
                deployment_state["url"] = f"http://{ip}"
        elif "Deployment URL:" in line:
            url = line.split("Deployment URL:")[1].strip()
            deployment_state["url"] = url


def run_deployment():
    """Runs the agent deployment logic inside a background thread."""
    original_stdout = sys.stdout
    interceptor = StreamInterceptor(original_stdout, _handle_agent_output)
    sys.stdout = interceptor

    try:
        agent.deploy()
        with state_lock:
            deployment_state["status"] = "success"
            success_msg = "✅ Deployed successfully!"
            if success_msg not in deployment_state["logs"]:
                deployment_state["logs"].append(success_msg)
            url = deployment_state.get("url")
            if url:
                url_msg = f"🌐 URL: {url}"
                if url_msg not in deployment_state["logs"]:
                    deployment_state["logs"].append(url_msg)
    except Exception as e:
        with state_lock:
            deployment_state["status"] = "failed"
            deployment_state["error"] = str(e)
            deployment_state["logs"].append(f"❌ Error: {e}")
    finally:
        sys.stdout = original_stdout


@app.route("/")
def index():
    try:
        return render_template("index.html")
    except Exception:
        return jsonify({"message": "AWS Deployment Agent API", "status": "online"})


@app.route("/deploy", methods=["POST"])
def deploy():
    with state_lock:
        if deployment_state["status"] == "running":
            return jsonify({
                "status": "running",
                "message": "Deployment is already in progress.",
                "logs": list(deployment_state["logs"]),
                "url": deployment_state["url"],
            }), 409

        deployment_state["status"] = "running"
        deployment_state["logs"] = ["🚀 Initializing deployment..."]
        deployment_state["url"] = None
        deployment_state["error"] = None

    thread = threading.Thread(target=run_deployment, daemon=True)
    thread.start()

    return jsonify({
        "status": "running",
        "message": "Deployment initiated.",
        "logs": list(deployment_state["logs"]),
        "url": deployment_state["url"],
    }), 202


@app.route("/status", methods=["GET"])
def status():
    with state_lock:
        return jsonify({
            "status": deployment_state["status"],
            "logs": list(deployment_state["logs"]),
            "url": deployment_state["url"],
            "error": deployment_state["error"],
        })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
