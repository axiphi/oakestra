import os

AGGREGATION_INTERVAL = int(os.environ.get("AGGREGATION_INTERVAL", 15))
# seconds; deploy command sent but no worker ACK yet
NODE_SCHEDULED_TIMEOUT = int(os.environ.get("NODE_SCHEDULED_TIMEOUT", 15))
