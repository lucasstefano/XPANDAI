import os
import time
import requests
import functions_framework
from flask import request, jsonify
from google.cloud import firestore

# Firestore Client Initialization
db = firestore.Client()

# Token de acesso do WB (1 hora)
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")

# Token de verificação do WB
WHATSAPP_VERIFICATION_TOKEN = os.getenv("WHATSAPP_VERIFICATION_TOKEN")

# ID da Helena cadastrada no WB
WHATSAPP_PHONE_NUMBER_ID = "598749756654857"

# URL da API do WhatsApp
WHATSAPP_API_URL = f"https://graph.facebook.com/v22.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"

@functions_framework.http
def whatsapp_webhook(request):
    """Processa mensagens recebidas do WhatsApp e salva no Firestore"""
    
    if request.method == "GET":
        # Verificação do webhook
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if token == WHATSAPP_VERIFICATION_TOKEN:
            return challenge, 200
        return "Token de verificação inválido", 403

    if request.method == "POST":
        req_data = request.get_json()

        if "entry" in req_data:
            for entry in req_data["entry"]:
                for change in entry["changes"]:
                    if "messages" in change["value"]:
                        for message in change["value"]["messages"]:
                            sender_id = message["from"]
                            user_message = message["text"]["body"]

                            print(f"📩 Nova mensagem do usuário {sender_id}: {user_message}")

                            # Salvar a mensagem no Firestore
                            save_message_to_firestore(sender_id, user_message)

        return jsonify({"status": "ok"}), 200

def save_message_to_firestore(sender_id, message):
    """Salva a mensagem do usuário no Firestore"""
    user_reference = db.collection("messages").document(sender_id)

    # Cria o registro da mensagem
    message_data = {
        "message": message,
        "sender_id": sender_id,
        "timestamp": firestore.SERVER_TIMESTAMP
    }

    # Salva ou atualiza a coleção de mensagens com base no sender_id
    user_reference.set(message_data, merge=True)

    print(f"💾 Mensagem salva no Firestore para o usuário {sender_id}")
 v