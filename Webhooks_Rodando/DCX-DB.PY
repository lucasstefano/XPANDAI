import json
 # Boa prática incluir, embora possa funcionar sem para HTTP simples
from google.cloud import firestore
from google.cloud import bigquery
from datetime import datetime

# Configurar o cliente do BigQuery
bq_client = bigquery.Client()

# Inicializa o cliente Firestore
db = firestore.Client()

def serialize_document(doc):
    """Converte valores do Firestore para formatos compatíveis com JSON."""
    serialized = {}
    for key, value in doc.items():
        if isinstance(value, (int, float)):  
            serialized[key] = value  
        elif isinstance(value, datetime):  
            serialized[key] = value.isoformat()  
        else:
            serialized[key] = value  
    return serialized

# Carregar credenciais do arquivo JSON
def query_bigquery():
    query = f'''
    SELECT * 
    FROM `helena-452318.imoveis.listing`
    LIMIT 1
    '''
    query_job = bq_client.query(query)
    results = query_job.result()
    listings = [dict(row) for row in results]

    return listings


def get_messages(document_id):
    """Obtém mensagens do Firestore e consulta o BigQuery com base nos dados."""
    session_id = f"{document_id}"
    try:
        # Obtém o documento do Firestore
        doc_ref = db.collection("messages").document(session_id)
        doc = doc_ref.get()

        if doc.exists:
            serialized_doc = serialize_document(doc.to_dict())
            preferences = serialized_doc.get("preferences", {})

            transactionType = preferences.get("transactionType", "") 
            propertyType = preferences.get("propertyType", "") 
            usageType = preferences.get("usageType", "") 

            location = preferences.get("location", "") 
            city = location.get("city", "") 
            state = location.get("state", "")
            address = location.get("address", "")
            neighborhood = location.get("neighborhood", "")
            complement = location.get("complement", "")
            zone = location.get("zone", "")

            bedroom = preferences.get("bedroom", "")
            bathroom = preferences.get("bathroom", "")
            garage = preferences.get("garage", "")
            suite = preferences.get("suite", "")

            unitFloor = preferences.get("unitFloor", "")
            floor = preferences.get("floor", "")
            buildings = preferences.get("buildings", "")

            area = preferences.get("area", "")
            livingArea = area.get("livingArea", "")
            lotArea = area.get("lotArea", "")

            price = preferences.get("price", "")
            valorMax = price.get("valorMax", "")
            valorMin = price.get("valorMin", "")

            features = preferences.get("features", "")
            requests = preferences.get("Requests", "")
           
            listings = query_bigquery()
         
          
            return json.dumps(listings, indent=2)
            
        else:
            return json.dumps({"error": "Documento não encontrado"}, indent=2)
    
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)

# Registra a função para ser acionada por HTTP.
# O Cloud Functions usará esta função como entry point.

def get_info():
    """
    Google Cloud Function HTTP que extrai um user_code opcional da URL,
    registra sua presença e retorna um JSON fixo com title e description.
    """
    # Dados fixos a serem enviados na resposta
    title = "User Information API"
    description = "API para retornar o título e a descrição."
    user_code = '226013'

    # Log no Cloud Logging (visível no Console do Google Cloud)
    if user_code:
        print(f"Código de usuário recebido: {user_code}")
    else:
        print("Nenhum código de usuário fornecido na URL path.")

    resposta = get_messages(user_code)
    print(resposta)
    resposta_json = json.loads(resposta)
    primeiro_item = resposta_json[0]
    imovel_code = primeiro_item.get('ListingID', 'ID não encontrado')
    description = f"Imóvel {primeiro_item.get('Title', 'Título não encontrado')}, do {primeiro_item.get('City', 'Cidade não encontrada')} com {primeiro_item.get('Bedrooms', 'N/A')} quartos, {primeiro_item.get('Bathrooms', 'N/A')} banheiros e {primeiro_item.get('GarageSpaces', 'N/A')} vagas de garagem. Preço de aluguel: R${primeiro_item.get('RentalPrice', 'N/A')}."


    response_data = {
        "title": imovel_code,
        "description": description
    }

    # Cria a resposta HTTP
    # (corpo JSON, status code 200 OK, header Content-Type)
    headers = {'Content-Type': 'application/json'}
    return (json.dumps(response_data), 200, headers)

get_info()