oye voy a generar las carpetas necesarias para generar el agente 2.



despues de ejecutar el script de youtube.py toda la información se irá a la colección que se muestra en las fotos, la estructura de la coleccion es la que te muestro a continuación





_id

69ed2ab331962803c5473ae1

video_id

"zMan_l2D67Y"

channel_id

"UCo411X24UFBU2HlRLWWSP6A"

channel_title

"SERVANDOZL"

collected_at

"2026-04-25T23:20:39.510459+00:00"

comment_count

3640



comments

Array (empty)

description

"Aqui puedes descargar este tema: http://www.mediafire.com/file/rhn5834…"

like_count

241157

published_at

"2017-05-07T00:30:00Z"

query

"gentedelmz corrido"



scoring

Object

source

"youtube"



tags

Array (19)

title

"Lenin Ramirez Ft. Regulo Caro - Somos Gente De Z4mbad4 (En Vivo 2017)"

url

"https://www.youtube.com/watch?v=zMan_l2D67Y"

view_count

81847104

caption

"false"

category_id

"10"

channel_country

"MX"

channel_created_at

"2014-06-24T07:22:23Z"

channel_description

"En este canal encontraras lo mas nuevo en la música de tus artistas fa…"

channel_keywords

""

channel_video_count

5907

channel_view_count

4115678792

default_audio_language

"es"

default_language

"es"

definition

"hd"

duration

"PT3M31S"

favorite_count

0

licensed_content

true

live_broadcast_content

"none"

localized_title

"Lenin Ramirez Ft. Regulo Caro - Somos Gente De Z4mbad4 (En Vivo 2017)"

subscriber_count

3110000

thumbnail_url

"https://i.ytimg.com/vi/zMan_l2D67Y/maxresdefault.jpg"



lo que quiero que hagas despues es filtrar aquellos con el sigueinte comando:



{ "comments.0": { $exists: true } }



para que filtres aquellos con comentarios, después a cada uno de los comentarios les vas a ejecutar el siguiente codigo



!pip install -q transformers accelerate bitsandbytes datasets scikit-learn torch huggingface_hub



from transformers import pipeline

# We use hugging face token

from google.colab import userdata

hf_token = userdata.get('hf_token')



# El modelo más potente para español sin entrenamiento adicional

classifier = pipeline("zero-shot-classification", model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli")



def format_classification_result(classification_result):

    labels = classification_result['labels']

    scores = classification_result['scores']

    formatted_dict = {}

    for i in range(len(labels)):

        formatted_dict[labels[i]] = scores[i]

    return formatted_dict



mensaje = 'Desde chile puro señor de los gallos 💪🏽'

etiquetas = ['Narcocultura', 'Oferta de Riesgo', 'Reclutamiento', 'Seguro']



res = classifier(mensaje, candidate_labels=etiquetas, hypothesis_template="Este mensaje es sobre {}.")



formatted_output = format_classification_result(res)

print(formatted_output)



el resultado del print debe ser añadido a la coleccion como 'resultado_preliminar'