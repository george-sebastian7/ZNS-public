import logging
import os
import sys

log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(log_dir, "chat.log")),
    ],
)

if not os.environ.get("CLAUDE_API_KEY"):
    print("Error: CLAUDE_API_KEY environment variable is required.")
    sys.exit(1)

from chat.app import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
