from confluent_kafka import Producer
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

KAFKA_BROKER = "localhost:9092"
TOPIC_NAME = "product-input"

producer = Producer({'bootstrap.servers': KAFKA_BROKER})

# Callback untuk laporan pengiriman pesan
def delivery_report(err, msg):
    if err:
        logging.error(f"Message delivery failed: {err}")
    else:
        logging.info(f"Message delivered to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()}")

# Fungsi untuk memvalidasi dan mengirim data ke Kafka
def send_to_kafka(raw_data):
    try:
        # Debugging: Log nilai raw_data
        logging.info(f"Raw data received: {raw_data}")

        # Validasi awal: pastikan raw_data adalah dict dan memiliki data
        if not isinstance(raw_data, dict):
            raise ValueError("Invalid input: raw_data must be a dictionary.")

        # Ekstrak fitur dari data mentah dengan validasi
        features = []

        # Ambil nilai rating, default 0 jika tidak ada atau invalid
        rating = raw_data.get("rating", 0)
        try:
            features.append(float(rating))
        except ValueError:
            logging.warning(f"Invalid rating: {rating}. Using default value 0.")
            features.append(0)

        # Ambil nilai product_id, default 0 jika tidak ada atau invalid
        product_id = raw_data.get("product_id", 0)
        try:
            features.append(int(product_id))
        except ValueError:
            logging.warning(f"Invalid product_id: {product_id}. Using default value 0.")
            features.append(0)

        # Ambil nilai shop_id, default 0 jika tidak ada atau invalid
        shop_id = raw_data.get("shop_id", 0)
        try:
            features.append(int(shop_id))
        except ValueError:
            logging.warning(f"Invalid shop_id: {shop_id}. Using default value 0.")
            features.append(0)

        # Ambil nilai sold, default 0 jika tidak ada atau invalid
        sold = raw_data.get("sold", 0)
        try:
            features.append(int(sold) if str(sold).strip().isdigit() else 0)
        except ValueError:
            logging.warning(f"Invalid sold: {sold}. Using default value 0.")
            features.append(0)

        # Debugging: Log nilai fitur sebelum validasi panjang
        logging.info(f"Extracted features before length validation: {features}")

        # Validasi panjang array: tambahkan nilai default jika kurang
        required_features = 5  # Jumlah fitur yang dibutuhkan oleh model
        if len(features) < required_features:
            features.extend([0] * (required_features - len(features)))  # Tambahkan nilai default (0)

        # Debugging: Log nilai fitur setelah validasi panjang
        logging.info(f"Extracted features after length validation: {features}")

        # Pastikan fitur tidak kosong atau invalid
        if not features or len(features) < required_features:
            raise ValueError("Invalid input: 'features' data is required and must match the expected structure.")

        # Buat pesan dengan format JSON
        message = {"features": features}

        # Kirim ke Kafka
        producer.produce(TOPIC_NAME, json.dumps(message), callback=delivery_report)
        producer.flush()

        logging.info(f"Message sent to Kafka: {message}")
    except ValueError as ve:
        logging.error(f"ValueError encountered: {ve}")
    except KeyError as ke:
        logging.error(f"KeyError encountered: {ke}")
    except Exception as e:
        logging.error(f"Error sending to Kafka: {str(e)}")
