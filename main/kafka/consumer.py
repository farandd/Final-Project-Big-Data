from confluent_kafka import Consumer
from minio import Minio
import json
import os
from datetime import datetime

KAFKA_BROKER = "localhost:9092"
TOPIC_NAME = "product-input"

minio_client = Minio(
    "localhost:9000",
    access_key="minio",
    secret_key="minio123",
    secure=False
)
BUCKET_NAME = "product-data"

# Pastikan bucket MinIO tersedia
if not minio_client.bucket_exists(BUCKET_NAME):
    minio_client.make_bucket(BUCKET_NAME)

consumer = Consumer({
    'bootstrap.servers': KAFKA_BROKER,
    'group.id': 'product-consumer',
    'auto.offset.reset': 'earliest'
})

consumer.subscribe([TOPIC_NAME])

def consume_messages():
    print("Consumer is running. Waiting for messages...")
    try:
        while True:
            msg = consumer.poll(1.0)  # Timeout 1 second
            if msg is None:
                continue
            if msg.error():
                print(f"Consumer error: {msg.error()}")
                continue

            # Decode and process the message
            try:
                # Load message as JSON
                data = json.loads(msg.value().decode('utf-8'))
                
                # Periksa apakah 'features' ada dalam data
                if 'features' not in data:
                    print(f"Invalid message format: {data}")
                    continue

                features = data['features']

                # Buat file JSON dari data features
                file_data = {"features": features}
                filename = f"features-{datetime.now().strftime('%Y%m%d%H%M%S')}.json"

                # Simpan ke file sementara
                with open(filename, 'w') as f:
                    json.dump(file_data, f)

                # Upload ke MinIO
                minio_client.fput_object(BUCKET_NAME, filename, filename)
                os.remove(filename)
                print(f"Saved data to MinIO: {filename}")

            except Exception as e:
                print(f"Error processing message: {e}")

    except KeyboardInterrupt:
        print("Consumer interrupted by user")
    finally:
        consumer.close()

if __name__ == "__main__":
    consume_messages()
