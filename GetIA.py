import os
import json
from google.cloud import firestore
from google.cloud import bigquery
from datetime import datetime
import vertexai  # Importar Vertex AI SDK
from vertexai.generative_models import GenerativeModel, Part  # Importar classes do modelo Generativo

# --- Configuração Inicial ---
# (Opcional mas recomendado: Pegar de variáveis de ambiente ou config)
GCP_PROJECT_ID = "helena-452318"  # Seu ID de projeto GCP
GCP_LOCATION = "us-central1"   # Ou a região que você prefere (ex: southamerica-east1 se suportado)

# Configurar o cliente do BigQuery
bq_client = bigquery.Client(project=GCP_PROJECT_ID)

# Inicializa o cliente Firestore
db = firestore.Client(project=GCP_PROJECT_ID)

# Inicializa o Vertex AI SDK
vertexai.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)

# Carrega o modelo Gemini que você quer usar
# Veja os modelos disponíveis na documentação do Vertex AI
# gemini-1.0-pro é um bom ponto de partida
gemini_model = GenerativeModel("gemini-1.0-pro")
# Ou para modelos mais recentes (verificar disponibilidade na sua região):
# gemini_model = GenerativeModel("gemini-1.5-pro-preview-0409")


def generate_property_description(listings):
    """Gera uma frase descritiva para cada imóvel listado."""
    descriptions = []
    for listing in listings:
        try:
            description = f"Imóvel encontrado: "
            # Descrição básica do imóvel
            description += f"{listing.get('PropertyType', 'Tipo não informado')} em {listing.get('City', 'Cidade não informada')}, {listing.get('State', 'Estado não informado')}, no bairro {listing.get('Neighborhood', 'Bairro não informado')}. "
            # Detalhes do imóvel
            description += f"Preço: R${listing.get('ListPrice', 0):.2f}. "
            description += f"Área útil: {listing.get('LivingArea', 'Não informada')} m². "
            description += f"Quartos: {listing.get('Bedroom', 'Não informado')}, Banheiros: {listing.get('Bathroom', 'Não informado')}, Suítes: {listing.get('Suite', 'Não informado')}, Garagem: {listing.get('Garage', 'Não informado')} vaga(s). "
            # Características adicionais
            if features := listing.get("Features"): # Python 3.8+ assignment expression
                description += f"Características: {features}. "
            descriptions.append(description)
        except KeyError as e:
            print(f"Erro ao acessar chave {e} para o imóvel {listing}. Pulando este imóvel.")
            descriptions.append(f"Erro ao processar dados para um imóvel.") # Adiciona info de erro
        except TypeError as e:
            print(f"Erro de tipo (provavelmente em ListPrice ou LivingArea) para o imóvel {listing}: {e}. Pulando este imóvel.")
            descriptions.append(f"Erro ao processar dados numéricos para um imóvel.") # Adiciona info de erro

    return descriptions

# --- MODIFICADO: query_bigquery agora retorna a lista de dicionários crus ---
def query_bigquery(transactionType, propertyType, usageType, city, state, neighborhood, zone, bedroom, bathroom, garage, suite, livingArea, price_min, price_max, features):
    """Consulta o BigQuery e retorna a lista de resultados crus."""

    # --- Validação e Conversão de Tipos ---
    # Garante que valores numéricos sejam números ou None/0 para filtros
    def safe_int(value, default=0):
        try:
            return int(value) if value not in (None, '') else default
        except (ValueError, TypeError):
            return default

    def safe_float(value, default=0.0):
        try:
            return float(value) if value not in (None, '') else default
        except (ValueError, TypeError):
            return default

    # Converte os parâmetros recebidos (que podem ser strings vazias do Firestore)
    # para os tipos corretos ou valores padrão para a query.
    param_bedroom = safe_int(bedroom, 0) # Se não informado, buscar a partir de 0 quartos
    param_bathroom = safe_int(bathroom, 0)
    param_garage = safe_int(garage, 0)
    param_suite = safe_int(suite, 0)
    param_livingArea = safe_int(livingArea, 0) # Ou talvez outro default se área mínima for importante
    param_price_min = safe_float(price_min, 0.0)
    param_price_max = safe_float(price_max, 999999999.0) # Um valor máximo alto como default

    # --- Construção Dinâmica da Query ---
    # Começa com a base da query e colunas necessárias
    query_base = f'''
    SELECT *
    FROM `helena-452318.imoveis.listing`
  
    '''
    # Lista para armazenar os parâmetros da query
    query_params = [
        bigquery.ScalarQueryParameter("transactionType", "STRING", transactionType),
        bigquery.ScalarQueryParameter("propertyType", "STRING", propertyType),
        bigquery.ScalarQueryParameter("usageType", "STRING", usageType),
        bigquery.ScalarQueryParameter("price_min", "FLOAT64", param_price_min),
        bigquery.ScalarQueryParameter("price_max", "FLOAT64", param_price_max),
    ]



    # Filtro de Features (exemplo com LIKE, requer que 'features' seja uma string de busca)
    # if features:
    #     query_base += " AND LOWER(Features) LIKE @features_pattern"
    #     query_params.append(bigquery.ScalarQueryParameter("features_pattern", "STRING", f"%{features.lower()}%"))


    # Adiciona Ordenação e Limite
    # Ordena pelo preço mais próximo ao MÁXIMO solicitado
    query = query_base + f'''
   
    LIMIT 10
    '''

    job_config = bigquery.QueryJobConfig(query_parameters=query_params)

    try:
        # Executa a consulta
        print(f"Executando Query BQ: {query}") # Para debug
        print(f"Com parâmetros: {[(p.name, p.value) for p in query_params]}") # Para debug
        query_job = bq_client.query(query, job_config=job_config)
        results = query_job.result()

        # Converte os resultados para um formato JSON (lista de dicionários)
        listings = [dict(row) for row in results]
        print(f"BigQuery encontrou {len(listings)} imóveis.") # Para debug
        return listings

    except Exception as e:
        print(f"Erro durante a consulta ao BigQuery: {e}")
        # Pode ser útil relançar o erro ou retornar uma lista vazia/None
        # raise e
        return []


# --- NOVA FUNÇÃO para chamar o Gemini ---
def call_gemini_with_descriptions(descriptions, task_instruction):
    """Envia as descrições e uma instrução para o Gemini e retorna a resposta."""
    if not descriptions:
        return "Nenhuma descrição de imóvel fornecida para o Gemini."

    # Combina as descrições em um único texto para o prompt
    descriptions_text = "\n\n".join(descriptions)

    # Monta o prompt completo
    prompt = f"{task_instruction}\n\n--- DESCRIÇÕES DOS IMÓVEIS ---\n\n{descriptions_text}"

    print("\n--- Enviando prompt para o Gemini ---")
    print(prompt)
    print("--- Fim do prompt ---\n")

    try:
        # Chama a API do Gemini (Vertex AI)
        # Configurações adicionais podem ser passadas em generation_config
        # Ex: generation_config={"temperature": 0.7, "max_output_tokens": 500}
        response = gemini_model.generate_content(prompt)

        print("--- Resposta do Gemini recebida ---")
        print(response.text)
        print("--- Fim da resposta ---\n")

        return response.text # Retorna apenas o texto da resposta

    except Exception as e:
        print(f"Erro ao chamar a API do Vertex AI (Gemini): {e}")
        return f"Erro ao gerar conteúdo com IA: {e}"


def serialize_document(doc):
    """Converte valores do Firestore para formatos compatíveis com JSON."""
    serialized = {}
    for key, value in doc.items():
        if isinstance(value, datetime):
            serialized[key] = value.isoformat() # Converte timestamps
        # Adicione outras conversões se necessário (GeoPoint, Reference, etc.)
        else:
            # Tenta manter o tipo original se for básico (str, int, float, bool, list, dict)
            # Se for um tipo complexo não tratado, converte para string como fallback
            if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                 serialized[key] = value
            else:
                 serialized[key] = str(value) # Fallback para string
    return serialized


# --- MODIFICADO: get_messages agora chama o Gemini ---
def get_messages(document_id):
    """Obtém mensagens do Firestore, consulta BigQuery e chama Gemini."""
    try:
        doc_ref = db.collection("messages").document(document_id)
        doc = doc_ref.get()

        if not doc.exists:
            return json.dumps({"error": "Documento não encontrado"}, indent=2)

        serialized_doc = serialize_document(doc.to_dict())
        dados_imoveis = serialized_doc.get("dados_imovel", {})

        # Extrai parâmetros com segurança, usando .get com defaults
        transactionType = dados_imoveis.get("transactionType", "")
        propertyType = dados_imoveis.get("propertyType", "")
        usageType = dados_imoveis.get("usageType", "")
        location = dados_imoveis.get("location", {})
        city = location.get("city", "")
        state = location.get("state", "")
        neighborhood = location.get("neighborhood", "")
        zone = location.get("zone", "") # Adicionado, mas não usado na query BQ atual
        bedroom = dados_imoveis.get("bedroom", 0) # Default 0
        bathroom = dados_imoveis.get("bathroom", 0) # Default 0
        garage = dados_imoveis.get("garage", 0) # Default 0
        suite = dados_imoveis.get("suite", 0) # Default 0
        livingArea = dados_imoveis.get("livingArea", 0) # Default 0
        listPrice = dados_imoveis.get("listPrice", {})
        price_min = listPrice.get("min", 0.0) # Default 0.0
        price_max = listPrice.get("max", 999999999.0) # Default alto
        features = dados_imoveis.get("features", "") # Pode ser usado para filtro LIKE

        # 1. Consultar BigQuery para obter os dados crus dos imóveis
        raw_listings = query_bigquery(
            transactionType, propertyType, usageType, city, state, neighborhood, zone,
            bedroom, bathroom, garage, suite, livingArea,
            price_min, price_max, features # Removido 'listPrice' como dict
        )

        response_data = {}

        if raw_listings:
            # 2. Gerar as descrições baseadas nos resultados do BigQuery
            property_descriptions = generate_property_description(raw_listings)
            response_data["original_descriptions"] = property_descriptions

            # 3. Definir a tarefa para o Gemini
            #    EXEMPLO: Criar um resumo atraente para um cliente
            gemini_task = (
                "Você é um assistente imobiliário virtual. "
                "Analise as descrições de imóveis encontradas abaixo. "
                "Crie um parágrafo curto e vendedor, destacando os pontos mais atraentes ou as melhores opções gerais "
                "para um potencial comprador interessado nesses critérios. Use um tom amigável e profissional."
                # "Se houver muitas opções, foque nas 2 ou 3 melhores." # Exemplo de instrução adicional
            )

            # 4. Chamar o Gemini com as descrições e a tarefa
            gemini_output = call_gemini_with_descriptions(property_descriptions, gemini_task)
            response_data["gemini_analysis"] = gemini_output

        else:
            # Se BigQuery não retornou nada
            response_data["message"] = "Nenhum imóvel encontrado no BigQuery com os critérios fornecidos."
            response_data["original_descriptions"] = []
            response_data["gemini_analysis"] = "Não há imóveis para analisar."

        return json.dumps(response_data, indent=2, ensure_ascii=False) # ensure_ascii=False para acentos

    except Exception as e:
        # Logar o erro completo pode ser útil aqui
        import traceback
        print(f"Erro geral em get_messages: {e}\n{traceback.format_exc()}")
        return json.dumps({"error": f"Ocorreu um erro inesperado: {e}"}, indent=2)


def main():
    # Para testes, pode fixar um ID ou pedir input
    # document_id = "ID_DO_SEU_DOCUMENTO_DE_TESTE"
    document_id = input("Digite o ID do documento Firestore: ").strip()

    if not document_id:
        print("ID do documento não pode ser vazio.")
        return

    response = get_messages(document_id)
    print("\n--- Resposta Final (JSON) ---")
    print(response)
    print("--- Fim da Resposta ---")

if __name__ == "__main__":
    main()