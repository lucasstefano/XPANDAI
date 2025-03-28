import os
import time
import requests 
import threading
import functions_framework
from flask import request, jsonify

from google.cloud import firestore
from google.cloud import dialogflowcx_v3beta1 as dialogflow_cx

WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_VERIFICATION_TOKEN = os.getenv("WHATSAPP_VERIFICATION_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = "598749756654857"
WHATSAPP_API_URL=f"https://graph.facebook.com/v22.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"

db = firestore.Client()
message_buffers = {}
message_locks = {}

def process_buffered_messages(sender_id):
    """ Aguarda 1 segundo de inatividade antes de enviar mensagens acumuladas. """
    time.sleep(1)
    with message_locks[sender_id]:
        if sender_id in message_buffers and message_buffers[sender_id]:
            combined_message = " \n".join(message_buffers[sender_id])
            resposta = enviar_para_dialogflow(sender_id, combined_message)
            enviar_mensagem_whatsapp(sender_id, resposta)
            del message_buffers[sender_id]

@functions_framework.http
def whatsapp_webhook(request):
    """Processa mensagens recebidas do WhatsApp e responde via Dialogflow CX"""
    
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if token == WHATSAPP_VERIFICATION_TOKEN:
            print(f"✅ Token válido. Enviando challenge...")
            return challenge, 200
        
        print(f"❌ Token inválido. Rejeitando conexão.")
        return "Token de verificação inválido", 403

    if request.method == "POST":
        req_data = request.get_json()
        
        print("📥 Webhook WhatsApp - Mensagem recebida:", req_data)

        if "entry" in req_data:
            for entry in req_data["entry"]:
                for change in entry["changes"]:
                    if "messages" in change["value"]:
                        for message in change["value"]["messages"]:
                            sender_id = message["from"]
                            user_message = message["text"]["body"]
                            
                            if aplicar_timeout(sender_id):
                                return jsonify({"status": "timeout"}), 200
                            
                            salva_mensagem_firestore(sender_id, user_message)
                            
                            if sender_id not in message_buffers:
                                message_buffers[sender_id] = []
                                message_locks[sender_id] = threading.Lock()
                            
                            with message_locks[sender_id]:
                                message_buffers[sender_id].append(user_message)
                                if len(message_buffers[sender_id]) > 5:
                                    message_buffers[sender_id].pop(0)
                            
                            threading.Thread(target=process_buffered_messages, args=(sender_id,)).start()

        return jsonify({"status": "ok"}), 200

def enviar_para_dialogflow(session_id, mensagem):
    """Envia a mensagem do usuário para o Dialogflow CX"""
    
    project_id = "helena-452318"
    location = "us-central1"
    agent_id = "954c8ddc-8cbd-4da0-81d4-1beab1afbfe4"

    client_options = {"api_endpoint": f"{location}-dialogflow.googleapis.com"}
    client = dialogflow_cx.SessionsClient(client_options=client_options)

    session_path = client.session_path(
        project=project_id,
        location=location,
        agent=agent_id,
        session=session_id
    )

    print(f"🔗 Sessão: {session_path}")
    
    text_input = dialogflow_cx.TextInput(text=mensagem)
    query_input = dialogflow_cx.QueryInput(text=text_input, language_code="pt-BR")

    request = dialogflow_cx.DetectIntentRequest(session=session_path, query_input=query_input)

    try:
        response = client.detect_intent(request=request)
        print(f"✅ Resposta do Dialogflow recebida com sucesso")
    except Exception as e:
        return "Erro ao processar a resposta"

    mensagens = response.query_result.response_messages

    if mensagens:
        resposta = mensagens[0].text.text[0] if mensagens[0].text.text else "Não entendi sua mensagem."
        print(f"🤖 Resposta do Dialogflow: {resposta}")
        return resposta

    print("⚠️ Nenhuma resposta válida do Dialogflow.")
    return "Erro ao processar a resposta"

def enviar_mensagem_whatsapp(destinatario, mensagem):
    """Envia uma mensagem de resposta via WhatsApp API."""
    
    print(f"📤 Enviando mensagem para WhatsApp")
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": destinatario,
        "type": "text",
        "text": {
            "body": mensagem
        }
    }

    response = requests.post(WHATSAPP_API_URL, headers=headers, json=data)

    print(f"📡 Status Code WhatsApp API: {response.status_code}")
    print(f"📩 Resposta API: {response.text}")

    return response.status_code

def salva_mensagem_firestore(sender_id, message):
    """Salva as últimas 5 mensagens do usuário no Firestore."""
    user_reference = db.collection("messages").document(sender_id)
    
    user_data = user_reference.get()
    messages = user_data.to_dict().get("messages", []) if user_data.exists else []
    
    messages.append({
        "message": message,
        "timestamp": firestore.SERVER_TIMESTAMP
    })
    
    if len(messages) > 5:
        messages.pop(0)
    
    user_reference.set({"messages": messages}, merge=True)
    print(f"💾 Mensagem salva no Firestore para o usuário {sender_id}")

def aplicar_timeout(sender_id):
    """Aplica um timeout de 10 segundos se o usuário enviar mensagens rapidamente."""
    user_reference = db.collection("users").document(sender_id)
    current_time = int(time.time())
    
    user_data = user_reference.get()

    if user_data.exists:
        data = user_data.to_dict()
        last_message_time = data.get("last_message_time", current_time)
        
        if current_time - last_message_time < 10:
            print(f"❌ Usuário {sender_id} está enviando mensagens com muita rapidez. Timeout aplicado!")
            return True
    
    user_reference.set({"last_message_time": current_time}, merge=True)
    return False
