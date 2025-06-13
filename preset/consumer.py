from confluent_kafka import Consumer, KafkaException
from minio import Minio
import json
import os
from datetime import datetime
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Kafka Consumer Configuration
consumer_config = {
    'bootstrap.servers': 'localhost:9092',  # Kafka broker
    'group.id': 'product-review-consumer',   # Consumer group ID
    'auto.offset.reset': 'earliest'         # Start reading from the earliest message
}

# Initialize Kafka Consumer
consumer = Consumer(consumer_config)

# Kafka Topic
topic = "product-review"

# MinIO Client Configuration
minio_client = Minio(
    'localhost:9000',  # MinIO server URL
    access_key='minio', 
    secret_key='minio123',  
    secure=False  # MinIO is running without TLS
)

# Create a MinIO Bucket (if it doesn't exist)
bucket_name = "product-review-bucket"
if not minio_client.bucket_exists(bucket_name):
    minio_client.make_bucket(bucket_name)
    logging.info(f"Bucket '{bucket_name}' created in MinIO.")
else:
    logging.info(f"Bucket '{bucket_name}' already exists.")

# Process and store the message in MinIO
def store_in_minio(message):
    try:
        # Create a unique file name using date and timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        file_name = f"product-review-{message['id']}-{timestamp}.json"

        # Save the message to a JSON file
        with open(file_name, 'w') as f:
            json.dump(message, f)

        # Upload to MinIO
        minio_client.fput_object(bucket_name, file_name, file_name)
        logging.info(f"Data uploaded to MinIO: {file_name}")

        # Clean up the local file
        os.remove(file_name)

    except Exception as e:
        logging.error(f"Error uploading to MinIO: {e}")


def consume_messages():
    # Subscribe to the Kafka topic
    consumer.subscribe([topic])
    logging.info(f"Subscribed to Kafka topic '{topic}'.")

    try:
        # Start consuming messages
        while True:
            messages = consumer.consume(num_messages=10, timeout=1.0)  # Consume up to 10 messages at a time
            if not messages:  # No messages available within the timeout
                continue

            for msg in messages:
                if msg.error():  # Error while fetching the message
                    logging.error(f"Kafka error: {msg.error()}")
                    continue
                try:
                    # Deserialize the message
                    message = json.loads(msg.value().decode('utf-8'))
                    logging.info(f"Message consumed: {message}")

                    # Extract and validate necessary fields
                    required_fields = ['id', 'text', 'rating', 'category', 'product_name', 'product_id', 'sold', 'shop_id', 'product_url']
                    if all(field in message for field in required_fields):
                        store_in_minio(message)
                    else:
                        logging.warning(f"Message missing required fields: {message}")
                except json.JSONDecodeError as e:
                    logging.error(f"Error decoding message: {e}")

    except KeyboardInterrupt:
        logging.info("Consuming stopped by user.")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
    finally:
        # Close the consumer when done
        consumer.close()
        logging.info("Kafka consumer closed.")

# Start consuming messages and storing them in MinIO
if __name__ == "__main__":
    consume_messages()
