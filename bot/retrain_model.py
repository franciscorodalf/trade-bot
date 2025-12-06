import logging
import json
from train_model import train

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

logging.basicConfig(filename=config['paths']['logs'], level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def retrain():
    logging.info("Starting automatic model retraining...")
    try:
        train()
        logging.info("Model retraining completed successfully.")
    except Exception as e:
        logging.error(f"Model retraining failed: {e}")

if __name__ == "__main__":
    retrain()
