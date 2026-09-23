import logging
import os

log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(log_dir, "visualizer.log")),
    ],
)

from visualizer.app import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081, debug=True)
