#------------------------------------------------------------------------------------------------------------------
from google.cloud import bigquery

# Configurar o cliente do BigQuery
client = bigquery.Client()

# Definir a consulta SQL
query = "SELECT * FROM `helena-452318.imoveis.listing`"

# Executar a consulta
query_job = client.query(query)  # Enviar a consulta ao BigQuery
results = query_job.result()  # Pegar os resultados

# Exibir os resultados
for row in results:
    print(f"ID: {row.ListingID}, Título: {row.Title}, Preço: {row.ListPrice}, Quartos: {row.Bedrooms}")

#------------------------------------------------------------------------------------------------------------------