from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from producer import send_to_kafka
from pipeline import get_predictions, load_model_and_scaler
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import LSTM, Dense, Input
from minio import Minio
import joblib
import os
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# MinIO Configuration
MINIO_CLIENT = Minio(
    "localhost:9000",
    access_key="minio",
    secret_key="minio123",
    secure=False
)
BUCKET_NAME = "product-model"
MODEL_NAME = "product_lstm_model.h5"
SCALER_NAME = "scaler.gz"

# Flask Configuration
app = Flask(__name__, static_folder='../web')
CORS(app)

# Load model and scaler on startup
def load_model_and_scaler():
    try:
        # Download model and scaler from MinIO
        model_path = f"/tmp/{MODEL_NAME}"
        scaler_path = f"/tmp/{SCALER_NAME}"
        
        MINIO_CLIENT.fget_object(BUCKET_NAME, MODEL_NAME, model_path)
        MINIO_CLIENT.fget_object(BUCKET_NAME, SCALER_NAME, scaler_path)
        
        model = load_model(model_path)
        scaler = joblib.load(scaler_path)
        os.remove(model_path)
        os.remove(scaler_path)
        
        return model, scaler
    except Exception as e:
        logging.error(f"Failed to load model or scaler: {str(e)}")
        raise

MODEL, SCALER = load_model_and_scaler()

@app.route('/')
def index():
    # Serve the static file for the frontend
    return send_from_directory('../web', 'index.html')

@app.route('/top-sold-products', methods=['GET'])
def top_sold_products():
    def parse_sold_value(sold_value):
        """
        Mengonversi nilai sold yang beragam format menjadi integer.
        Jika format tidak valid, return None.
        """
        try:
            if isinstance(sold_value, str):
                # Hilangkan spasi dan ubah ke huruf kecil
                sold_value = sold_value.lower().replace(',', '').strip()
                # Tangani format "rb" (ribuan)
                if 'rb' in sold_value:
                    sold_value = sold_value.replace('rb', '')
                    return int(float(sold_value) * 1000)
                # Tangani format biasa
                return int(sold_value)
            elif isinstance(sold_value, (int, float)):
                return int(sold_value)
        except ValueError:
            return None  # Nilai tidak valid
        return None

    try:
        valid_categories = ["elektronik", "fashion", "olahraga", "handphone", "pertukangan"]
        category_filter = request.args.get('category')

        if category_filter and category_filter.lower() not in valid_categories:
            return jsonify({"error": f"Category '{category_filter}' not found. Valid categories are: {', '.join(valid_categories)}"}), 400

        objects = MINIO_CLIENT.list_objects("product-review-bucket", recursive=True)
        product_data = []

        for obj in objects:
            try:
                response = MINIO_CLIENT.get_object("product-review-bucket", obj.object_name)
                product = json.loads(response.read().decode('utf-8'))
                response.close()
                response.release_conn()

                if 'product_name' in product and 'sold' in product:
                    sold_value = parse_sold_value(product['sold'])
                    if sold_value is None:
                        logging.warning(f"Invalid sold value for product {product.get('product_name', 'unknown')}: {product['sold']}")
                        continue  # Lewati produk ini jika sold tidak valid

                    product_entry = {
                        "product_name": product['product_name'],
                        "sold": sold_value,
                        "category": product.get('category', 'Uncategorized')
                    }
                    product_data.append(product_entry)
            except json.JSONDecodeError:
                logging.warning(f"Failed to parse JSON in file {obj.object_name}")
            except Exception as e:
                logging.warning(f"Failed to process file {obj.object_name}: {str(e)}")
                continue

        if not product_data:
            return jsonify({"error": "No valid product data found"}), 404

        if category_filter:
            product_data = [p for p in product_data if p['category'].lower() == category_filter.lower()]

        product_data = sorted(product_data, key=lambda x: x['sold'], reverse=True)
        top_products = product_data[:10]

        return jsonify({"top_products": top_products})

    except Exception as e:
        logging.error(f"Error in /top-sold-products: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/predict', methods=['POST'])
def predict():
    try:
        data = request.json
        features = data.get('features')

        if not features or len(features) != 2:
            return jsonify({"error": "Invalid input, 2 features ('category', 'sold') required"}), 400

        category = int(features[0])  # Integer untuk kategori
        sold = float(features[1])    # Float untuk sold

        # Skala input jika diperlukan
        input_features = np.array([[category, sold]])
        scaled_features = SCALER.transform(input_features).reshape(1, 1, -1)

        # Prediksi
        predictions = MODEL.predict(scaled_features).tolist()
        predicted_sales = max(0, predictions[0][0])

        return jsonify({"product": f"Category {category}", "sales": predicted_sales})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/train', methods=['POST'])
def train():
    global MODEL, SCALER
    try:
        logging.info("Starting the training process...")

        # Data pengguna dikirim dalam request
        data = request.json
        user_data = data.get("sales", [])
        category_codes = data.get("categories", [])

        if not user_data or not category_codes:
            return jsonify({"error": "Sales and categories data are required for training"}), 400

        sales = np.array(user_data).reshape(-1, 1)
        category_codes = np.array(category_codes).reshape(-1, 1)
        combined_data = np.hstack([sales, category_codes])

        scaler = MinMaxScaler()
        data_scaled = scaler.fit_transform(combined_data)

        sequence_length = 5
        X, y = [], []
        for i in range(len(data_scaled) - sequence_length):
            X.append(data_scaled[i:i + sequence_length])
            y.append(data_scaled[i + sequence_length][0])

        X = np.array(X)
        y = np.array(y)

        input_shape = (X.shape[1], X.shape[2])

        model = Sequential([
            Input(shape=input_shape),
            LSTM(50, activation='relu'),
            Dense(1, activation='relu')
        ])

        model.compile(optimizer='adam', loss='mae')
        model.fit(X, y, epochs=20, batch_size=16, verbose=2)

        local_model_path = MODEL_NAME
        model.save(local_model_path)
        MINIO_CLIENT.fput_object(BUCKET_NAME, MODEL_NAME, local_model_path)

        local_scaler_path = SCALER_NAME
        joblib.dump(scaler, local_scaler_path)
        MINIO_CLIENT.fput_object(BUCKET_NAME, SCALER_NAME, local_scaler_path)

        os.remove(local_model_path)
        os.remove(local_scaler_path)

        MODEL, SCALER = load_model_and_scaler()

        return jsonify({"message": "Model training completed and updated successfully"})

    except Exception as e:
        logging.error(f"Error during training: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
