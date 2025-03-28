import functions_framework
import json
import traceback
from flask import Request, make_response
from google.cloud import firestore

# Inicializa o cliente Firestore
db = firestore.Client()

@functions_framework.http
def registrar_criterios_busca(request: Request):
    """
    Recebe critérios de busca imobiliária do Dialogflow CX e armazena no Firestore.
    """
    if request.method != 'POST':
        return make_response(json.dumps({"status": "error", "message": "Método não permitido"}), 405)

    try:
        request_json = request.get_json(silent=True)
        if not request_json:
            return make_response(json.dumps({"status": "error", "message": "Requisição inválida (JSON esperado)"}), 400)

        # Obtém os parâmetros do JSON recebido
        dialogflow_session_id = request_json.get("dialogflowSessionId", "desconhecido")
        property_type = request_json.get("propertyType", "Desconhecido")
        transaction_type = request_json.get("transactionType", "Desconhecido")
        usage_type = request_json.get("usageType", "Desconhecido")

        location = request_json.get("location", {})
        city = location.get("city", "Não informado")
        state = location.get("state", "Não informado")
        neighborhood = location.get("neighborhood", "Não informado")
        address = location.get("address", "Não informado")
        zone = location.get("zone", "Não informado")

        list_price = request_json.get("listPrice", {})
        min_price = list_price.get("min", 0)
        max_price = list_price.get("max", 0)
        price_description = list_price.get("descricao", "Não informado")

        living_area = request_json.get("livingArea", 0)
        bedrooms = request_json.get("bedroom", 0)
        bathrooms = request_json.get("bathroom", 0)
        suites = request_json.get("suite", 0)
        garages = request_json.get("garage", 0)
        features = request_json.get("features", [])
        if not isinstance(features, list):
            features = []

        # Log dos dados recebidos
        print(f"""
        Dados recebidos:
        Dialogflow Session ID: {dialogflow_session_id}
        Tipo de Imóvel: {property_type}
        Tipo de Transação: {transaction_type}
        Tipo de Uso: {usage_type}
        Localização: {city}, {state}, {neighborhood}, {address}, {zone}
        Preço: Min {min_price}, Max {max_price}, Descrição: {price_description}
        Área: {living_area}m², Quartos: {bedrooms}, Banheiros: {bathrooms}, Suítes: {suites}, Vagas: {garages}
        Features: {', '.join(features) if features else 'Nenhuma'}
        """)

        # Salvar no Firestore
        success = save_on_firestore(dialogflow_session_id, {
            "propertyType": property_type,
            "transactionType": transaction_type,
            "usageType": usage_type,
            "location": {
                "city": city,
                "state": state,
                "neighborhood": neighborhood,
                "address": address,
                "zone": zone
            },
            "listPrice": {
                "min": min_price,
                "max": max_price,
                "descricao": price_description
            },
            "livingArea": living_area,
            "bedroom": bedrooms,
            "bathroom": bathrooms,
            "suite": suites,
            "garage": garages,
            "features": features
        })

        if not success:
            return make_response(json.dumps({"status": "error", "message": "Erro ao salvar no Firestore"}), 500)

        response_data = {
            "status": "success",
            "message": f"Critérios registrados com ID {dialogflow_session_id}.",
            "dados_recebidos": request_json
        }
        return make_response(json.dumps(response_data), 200)

    except Exception as e:
        print(f"Erro ao processar requisição: {e}")
        print(traceback.format_exc())
        return make_response(json.dumps({"status": "error", "message": "Erro interno"}), 500)

def save_on_firestore(session_id, search_criteria):
    """Salva os critérios de busca no Firestore"""
    try:
        doc_ref = db.collection("messages").document(session_id)
        data_to_store = {
            "session_id": session_id,
            "dados_imovel": search_criteria,
            "timestamp": firestore.SERVER_TIMESTAMP
        }
        doc_ref.set(data_to_store, merge=True)
        print(f"💾 Critérios de busca salvos no Firestore para a sessão {session_id}")
        return True
    except Exception as e:
        print(f"❌ Erro ao salvar no Firestore: {e}")
        return False