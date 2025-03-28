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
        dialogflow_session_id = request_json.get("dialogflowSessionId", "Desconhecido")
        transaction_type = request_json.get("transactionType", "N/A")
        property_type = request_json.get("propertyType", "N/A")

        location = request_json.get("location", {})
        city = location.get("city", "N/A")
        state = location.get("state", "N/A")
        neighborhood = location.get("neighborhood", "N/A")
        address = location.get("address", "N/A")
        complement = location.get("complement", "N/A")
        zone = location.get("zone", "N/A")  
       

       
        bedroom = request_json.get("bedroom", -1)
        bathroom = request_json.get("bathroom", -1)
        suite = request_json.get("suite", -1)

        floor = request_json.get("floor", -1)
        unitFloor = request_json.get("unitFloor", -1)
        buildings = request_json.get("buildings", -1)
        garages = request_json.get("garage", -1)

        area = request_json.get("area", {})
        lotArea = area.get("lotArea", -1)
        livingArea = area.get("livingArea", -1)

        price = request_json.get("price", {})
        valorMin = price.get("valorMin", -1)
        valorMax = price.get("valorMax", -1)
        description = price.get("description", None)
        usage_type = request_json.get("usageType", "N/A")

        features = request_json.get("features", [])
        especialRequests = request_json.get("especialRequests", [])
        
        if not isinstance(features, list):
            features = []

        # Log dos dados recebidos
        print(f"""
        Dados recebidos:
        Dialogflow Session ID: {dialogflow_session_id}
        Tipo de Imóvel: {property_type}
        Tipo de Transação: {transaction_type}
        Tipo de Uso: {usage_type}
        Localização: {city}, {state}, {neighborhood}, {address},{complement}, {zone}
        Preço: Min {valorMin}, Max {valorMax}
        Andar: {floor}{unitFloor}{buildings} andares,
        Área: {lotArea + livingArea}m², Quartos: {bedroom}, Banheiros: {bathroom}, Suítes: {suite}, Vagas: {garages}
        Features: {', '.join(features) if features else 'Nenhuma'}
        Pedidos: {', '.join(especialRequests) if especialRequests else 'Nenhuma'}
        """)

        # Salvar no Firestore
        success = save_on_firestore(dialogflow_session_id, {
            "transactionType": transaction_type,
            "propertyType": property_type,
            "location": {
                "city": city,
                "state": state,
                "neighborhood": neighborhood,
                "address": address,
                "complement": complement,
                "zone": zone
            },
            "bedroom": bedroom,
            "bathroom": bathroom,
            "suite": suite,
            "floor": floor,
            "unitFloor": unitFloor,
            "buildings": buildings,
            "garage": garages,
            "area": {
                "lotArea": lotArea,
                "livingArea": livingArea,
            },
            "price": {
                "valorMin": valorMin,
                "valorMax": valorMax,
                "description": description 
            },
            "usageType": usage_type,
            "features": features,
            "Requests": especialRequests
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
            "preferences": search_criteria,
        }
        doc_ref.set(data_to_store, merge=True)
        print(f"💾 Critérios de busca salvos no Firestore para a sessão {session_id}")
        return True
    except Exception as e:
        print(f"❌ Erro ao salvar no Firestore: {e}")
        return False