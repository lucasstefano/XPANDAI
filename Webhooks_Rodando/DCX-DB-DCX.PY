import json
import functions_framework  # Boa prática incluir, embora possa funcionar sem para HTTP simples
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
def query_bigquery(exclude_ids):
    """Consulta o BigQuery e exclui os imóveis já visualizados."""
    exclude_filter = ""
    
    if exclude_ids:
        # Formatar os IDs para a cláusula WHERE do SQL
        exclude_filter = f"WHERE ListingID NOT IN ({', '.join([f'\"{id}\"' for id in exclude_ids])})"

    query = f'''
    SELECT * 
    FROM `helena-452318.imoveis.listing`
    {exclude_filter}
    LIMIT 1
    '''
    query_job = bq_client.query(query)
    results = query_job.result()
    listings = [dict(row) for row in results]

    return listings

def get_visualized_imoveis(user_code):
    """Obtém a lista de imóveis já visualizados do Firestore para o usuário."""
    try:
        doc_ref = db.collection("messages").document(user_code)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            return data.get("imoveis_ja_visualizados", [])
        return []
    except Exception as e:
        print(f"Erro ao buscar imóveis visualizados: {e}")
        return []

def get_messages(document_id):
    """Obtém mensagens do Firestore e consulta o BigQuery evitando imóveis já visualizados."""
    session_id = f"{document_id}"
    try:
        doc_ref = db.collection("messages").document(session_id)
        doc = doc_ref.get()

        if doc.exists:
            serialized_doc = serialize_document(doc.to_dict())

            # Buscar imóveis já visualizados
            visualized_imoveis = get_visualized_imoveis(session_id)

            # Consultar BigQuery excluindo os imóveis já vistos
            listings = query_bigquery(visualized_imoveis)

            return json.dumps(listings, indent=2)
        else:
            return json.dumps({"error": "Documento não encontrado"}, indent=2)
    
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)

def save_imovel_to_firestore(user_code, imovel_code):
    """Salva o código do imóvel visualizado no Firestore para um usuário específico."""
    try:
        # Referência ao documento do usuário no Firestore
        doc_ref = db.collection("messages").document(user_code)
        doc = doc_ref.get()

        if doc.exists:
            data = doc.to_dict()
            imoveis_visualizados = data.get("imoveis_ja_visualizados", [])

            # Adiciona apenas se ainda não estiver na lista
            if imovel_code not in imoveis_visualizados:
                imoveis_visualizados.append(imovel_code)
                doc_ref.update({"imoveis_ja_visualizados": imoveis_visualizados})
        else:
            # Cria um novo documento caso não exista
            doc_ref.set({"imoveis_ja_visualizados": [imovel_code]})

    except Exception as e:
        print(f"Erro ao salvar imóvel no Firestore: {e}")

@functions_framework.http
def get_info(request):
    """API HTTP para retornar imóveis que o usuário ainda não visualizou."""
    user_code = request.args.get('user_code') 

    if not user_code:
        return json.dumps({"error": "user_code não fornecido"}), 400

    resposta = get_messages(user_code)
    resposta_json = json.loads(resposta)

    if not resposta_json or "error" in resposta_json:
        return json.dumps({"error": "Nenhum imóvel encontrado"}), 404

    primeiro_item = resposta_json[0]
    imovel_code = primeiro_item.get('ListingID', 'ID não encontrado')
    description = f"Imóvel {primeiro_item.get('Title', 'Título não encontrado')}, {primeiro_item.get('City', 'Cidade não encontrada')} com {primeiro_item.get('Bedrooms', 'N/A')} quartos, {primeiro_item.get('Bathrooms', 'N/A')} banheiros e {primeiro_item.get('GarageSpaces', 'N/A')} vagas de garagem. Preço de aluguel: R${primeiro_item.get('RentalPrice', 'N/A')}."

    # Salvar imóvel visualizado no Firestore
    save_imovel_to_firestore(user_code, imovel_code)

    response_data = {
        "title": imovel_code,
        "description": description
    }

    headers = {'Content-Type': 'application/json'}
    return json.dumps(response_data), 200, headers
