from confluent_kafka import Producer
import pandas as pd
import json
import os

# Konfigurasi Kafka
KAFKA_BROKER = "localhost:9092"
TOPIC_NAME = "product-review"

# Konfigurasi Kafka Producer
conf = {
    'bootstrap.servers': KAFKA_BROKER,
    'client.id': 'product-review-producer'
}

producer = Producer(conf)

print("Kafka Producer siap...")

# Fungsi untuk melaporkan hasil pengiriman pesan
def delivery_report(err, msg):
    if err:
        print(f"Pengiriman pesan gagal: {err}")
    else:
        print(f"Pesan terkirim ke topic {msg.topic()} [partisi {msg.partition()}] @ offset {msg.offset()}")

# Path ke file dataset
DATASET_PATH = "product_reviews_dirty.csv"

# Memeriksa keberadaan file
if not os.path.exists(DATASET_PATH):
    print(f"File {DATASET_PATH} tidak ditemukan. Pastikan file tersedia.")
    exit(1)

# Load dataset
try:
    df = pd.read_csv(DATASET_PATH)
    print(f"Dataset berhasil dimuat. Total {len(df)} baris data.")
except Exception as e:
    print(f"Gagal membaca dataset: {e}")
    exit(1)

# Iterasi dataset dan kirim pesan ke Kafka
for index, row in df.iterrows():
    try:
        # Validasi data
        if pd.notna(row['id']) and pd.notna(row['text']) and pd.notna(row['rating']):
            message = {
                "id": row["id"],
                "text": row["text"],
                "rating": row["rating"],
                "category": row["category"],
                "product_name": row["product_name"],
                "product_id": row["product_id"],
                "sold": row["sold"],
                "shop_id": row["shop_id"],
                "product_url": row["product_url"]
            }
            
            # Kunci pesan (berdasarkan ID produk)
            key = str(row["id"])
            
            # Kirim pesan ke Kafka
            producer.produce(
                topic=TOPIC_NAME,
                key=key,
                value=json.dumps(message),
                callback=delivery_report
            )
            
            producer.poll(0)  # Memberi waktu untuk callback
            
        else:
            print(f"Data kosong atau tidak valid pada indeks {index}, dilewati.")
    
    except Exception as e:
        print(f"Error saat mengirim data indeks {index}: {e}")

# Tunggu semua pesan selesai dikirim
producer.flush()
print("Semua pesan telah berhasil dikirim ke Kafka.")
