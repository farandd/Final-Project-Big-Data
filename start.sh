#!/bin/sh

# Menjalankan Docker Compose
docker-compose up -d

# Membuat topic Kafka
docker exec -it kafka kafka-topics.sh --create --topic product-review --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
docker exec -it kafka kafka-topics.sh --create --topic product-input --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1

# Menjalankan train.py
cd preset && python3 train.py
cd ..

# Menjalankan producer.py
cd preset && python3 producer.py
cd ..

# Menjalankan consumer.py di latar belakang
python3 preset/consumer.py &
CONSUMER_PID=$!  # Menyimpan PID proses consumer.py

echo "Consumer berjalan dengan PID: $CONSUMER_PID"

# Menunggu input untuk menutup consumer.py
read -p "Tekan [Enter] untuk menghentikan consumer..."

# Menghentikan consumer.py
kill $CONSUMER_PID
echo "Consumer dihentikan."
