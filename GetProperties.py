import os
import json
from google.cloud import firestore
from google.cloud import bigquery
from datetime import datetime

# Configurar o cliente do BigQuery
bq_client = bigquery.Client()

# Inicializa o cliente Firestore
db = firestore.Client()

def generate_property_description(listings):
    """Gera uma frase descritiva para cada imóvel listado."""
    descriptions = []
    for listing in listings:
        try:
            description = f"Imóvel encontrado: "
            
            # Descrição básica do imóvel
            description += f"{listing['PropertyType']} em {listing['City']}, {listing['State']}, no bairro {listing['Neighborhood']}. "

            # Detalhes do imóvel
            description += f"Preço: R${listing['ListPrice']:.2f}. "
            description += f"Área útil: {listing['LivingArea']} m². "
            description += f"Quartos: {listing.get('Bedroom', 0)}, Banheiros: {listing.get('Bathroom', 0)}, Suítes: {listing.get('Suite', 0)}, Garagem: {listing.get('Garage', 0)} vaga(s). "
            
            # Características adicionais
            if listing.get("Features"):
                description += f"Características: {listing['Features']}. "
            
            descriptions.append(description)
        except KeyError as e:
            print(f"Erro ao acessar chave {e} para o imóvel {listing}")
    
    return descriptions

def query_bigquery(transactionType, propertyType, usageType, city, state, neighborhood, zone, bedroom, bathroom, garage, suite, livingArea, price_min, price_max, listPrice, features):
    query = f'''
    SELECT * 
    FROM `helena-452318.imoveis.listing`
    LIMIT 10
    '''

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("city", "STRING", city),
            bigquery.ScalarQueryParameter("transactionType", "STRING", transactionType),
            bigquery.ScalarQueryParameter("propertyType", "STRING", propertyType),
            bigquery.ScalarQueryParameter("usageType", "STRING", usageType),
            bigquery.ScalarQueryParameter("state", "STRING", state),
            bigquery.ScalarQueryParameter("neighborhood", "STRING", neighborhood),
            bigquery.ScalarQueryParameter("zone", "STRING", zone),
            bigquery.ScalarQueryParameter("bedroom", "INT64", bedroom),
            bigquery.ScalarQueryParameter("bathroom", "INT64", bathroom),
            bigquery.ScalarQueryParameter("garage", "INT64", garage),
            bigquery.ScalarQueryParameter("suite", "INT64", suite),
            bigquery.ScalarQueryParameter("livingArea", "INT64", livingArea),
            bigquery.ScalarQueryParameter("price_min", "FLOAT64", price_min),
            bigquery.ScalarQueryParameter("price_max", "FLOAT64", price_max),
            bigquery.ScalarQueryParameter("features", "STRING", features)
        ]
    )
    
    # Executa a consulta
    query_job = bq_client.query(query, job_config=job_config)
    results = query_job.result()

    # Converte os resultados para um formato JSON
    listings = [dict(row) for row in results]

    # Gerar descrições a partir dos dados dos imóveis
    descriptions = generate_property_description(listings)
    
    return descriptions

def serialize_document(doc):
    """Converte valores do Firestore para formatos compatíveis com JSON."""
    serialized = {}
    for key, value in doc.items():
        if isinstance(value, (int, float)):  
            serialized[key] = value  # Mantém números sem conversão
        elif isinstance(value, datetime):  
            serialized[key] = value.isoformat()  # Converte timestamps para string ISO 8601
        else:
            serialized[key] = value  # Mantém strings e outros valores inalterados
    return serialized

def get_messages(document_id):
    """Obtém mensagens do Firestore e consulta o BigQuery com base nos dados."""
    try:
        # Obtém o documento do Firestore
        doc_ref = db.collection("messages").document(document_id)
        doc = doc_ref.get()

        if doc.exists:
            serialized_doc = serialize_document(doc.to_dict())
            dados_imoveis = serialized_doc.get("dados_imovel", {})

            transactionType = dados_imoveis.get("transactionType","") #Comprar ou Vender
            propertyType = dados_imoveis.get("propertyType","") # Casa ou Apartamento
            usageType = dados_imoveis.get("usageType","") # Residencial ou Trabalho

            location = dados_imoveis.get("location", "") 
            city = location.get("city", "") 
            state = location.get("state", "")
            neighborhood = location.get("neighborhood","")
            zone = location.get("zone","")

            bedroom = dados_imoveis.get("bedroom","")
            bathroom = dados_imoveis.get("bathroom","")
            garage = dados_imoveis.get("garage","")
            suite = dados_imoveis.get("suite","")

            livingArea = dados_imoveis.get("livingArea","")

            listPrice = dados_imoveis.get("listPrice","")
            min = listPrice.get("min","")
            max = listPrice.get("max","")

            features = dados_imoveis.get("features","")
           
            listings = query_bigquery(transactionType, propertyType, usageType, city, state, neighborhood, zone, bedroom, bathroom, garage, suite, livingArea, min, max, listPrice, features)
            response_data = {
                "bigquery_results": listings
            }
            return json.dumps(response_data, indent=2)
            
        
        else:
            return json.dumps({"error": "Documento não encontrado"}, indent=2)
    
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


def main():
    document_id = input("Digite o ID do documento: ").strip()
    response = get_messages(document_id)
    print(response)

main()