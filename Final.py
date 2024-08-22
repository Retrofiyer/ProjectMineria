import gradio as gr
import requests
import json
import time
from PIL import Image
import io
import tempfile

# Configuración de la API de Leonardo.AI
api_key = "91570e4e-9f73-463b-89e5-129c47ccb9f4"  # Asegúrate de usar tu propia API key
authorization = f"Bearer {api_key}"

headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "authorization": authorization
}

def get_presigned_url():
    url = "https://cloud.leonardo.ai/api/rest/v1/init-image"
    payload = {"extension": "jpg"}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()['uploadInitImage']

def upload_image(image):
    init_image_info = get_presigned_url()
    fields = json.loads(init_image_info['fields'])
    upload_url = init_image_info['url']
    image_id = init_image_info['id']

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
        image.save(temp_file.name)
        with open(temp_file.name, 'rb') as f:
            files = {'file': f}
            response = requests.post(upload_url, data=fields, files=files)
            response.raise_for_status()

    return image_id

def get_generated_images(generation_id):
    url = f"https://cloud.leonardo.ai/api/rest/v1/generations/{generation_id}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json().get('generations_by_pk', {}).get('generated_images', [])

def generate_image(image, breed_description, style, gender):
    try:
        image_id = upload_image(image)

        # Determinar el prompt en función de la raza, estilo y género
        if style == 'Estilo extremadamente corto':
            prompt = (
                f"Create a highly detailed, photorealistic image of a {gender} {breed_description} with extremely short, well-groomed fur. "
                "The fur should appear neatly trimmed across the entire body, including the face, ears, legs, and tail. "
                "Emphasize the sleek, polished look of the coat, with clean lines and minimal fluffiness. The face should have a clear, sharp appearance, with the eyes fully visible and the ears free of any tangles. "
                "Highlight the breed's distinctive features and convey a sense of sophistication and elegance. "
                "Ensure that all parts of the dog—such as the position, ears, eyes, muzzle, tongue, teeth, legs, and tail—are identical to those in the provided reference image."
            )

        elif style == 'Estilo señorita popular' and gender == 'Hembra':
            prompt = (
                f"Create a beautifully detailed, photorealistic image of a {gender} {breed_description} with long, luxurious fur. "
                "The fur should be meticulously styled and well-maintained, especially on the face, ears, legs, and tail. "
                "The face should have soft, flowing fur, framing the eyes gently, with the ears draped in elegant, cascading fur. "
                "The legs and tail should feature long, silky fur that moves gracefully. The overall appearance should exude sophistication, femininity, and refined charm."
            )
        elif style == 'Estilo macho' and gender == 'Macho':
            prompt = (
                f"Create a detailed, photorealistic image of a {gender} {breed_description} with long, stately fur. "
                "The fur should be sleek yet flowing, especially on the mane, tail, and legs, showcasing a majestic and powerful appearance. "
                "The face should be framed by fur that enhances the breed's strong features, with ears that are covered in well-groomed, smooth fur. "
                "The overall look should convey strength, elegance, and a regal presence, befitting the breed's noble characteristics."
            )
        else:
            return [f"Raza desconocida: {breed_description}"]

        negative_prompt = (
            "Avoid any unkempt or tangled fur. Ensure the fur is consistent with the chosen style, with no elements of the opposite style present. "
            "Focus solely on the dog, with a neutral or simple background that does not detract from the dog's appearance."
        )
        
        url = "https://cloud.leonardo.ai/api/rest/v1/generations"
        payload = {
            "height": 512,
            "width": 512,
            "modelId": "b24e16ff-06e3-43eb-8d33-4416c2d75876",
            "prompt": prompt,
            "init_image_id": image_id,
            "init_strength": 0.5,
            "negative_prompt": negative_prompt,
            "alchemy": True,
            "photoReal": True,
            "photoRealVersion": "v2",
            "presetStyle": "CINEMATIC"
        }
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        generation_id = response.json().get('sdGenerationJob', {}).get('generationId')
        if not generation_id:
            raise ValueError("No generation ID returned from Leonardo.ai.")

        for _ in range(10):
            time.sleep(20)
            generated_images = get_generated_images(generation_id)
            if generated_images:
                image_urls = [img['url'] for img in generated_images[:4]]
                images = []
                for image_url in image_urls:
                    image_response = requests.get(image_url)
                    image_response.raise_for_status()
                    images.append(Image.open(io.BytesIO(image_response.content)))
                return images

        raise ValueError("No generated images found after waiting.")
    except Exception as e:
        return [f"An error occurred: {e}"]

def classify_image(image):
    if image is None or isinstance(image, str):
        return "Error: No se ha subido una imagen de un perro.", None

    url = 'https://mineriamodel.onrender.com/classify'
    
    # Convertir la imagen a bytes
    image_bytes = io.BytesIO()
    image.save(image_bytes, format='JPEG')
    image_bytes.seek(0)
    
    try:
        # Enviar la solicitud POST
        response = requests.post(
            url,
            files={'file': ('image.jpg', image_bytes, 'image/jpeg')}
        )
        response.raise_for_status()
        
        result = response.json()
        
        breed_description = result.get('breed', 'Unknown breed')
        probability_percentage = result.get('probability', 0)
        
        if probability_percentage < 80.99:
            return "Raza: Indefinida o imagen no válida", None
        
        return breed_description, probability_percentage

    except requests.exceptions.HTTPError as http_err:
        return f"HTTP error occurred: {http_err}", None
    except requests.exceptions.RequestException as req_err:
        return f"Error occurred: {req_err}", None
    except ValueError as json_err:
        return f"Error decoding JSON response: {json_err}", None

def combined_function(image, style, gender):

    if image is None:
        return "Error: Por favor, sube una imagen de un perro antes de continuar.", "N/A", None, None, None, None
    
    if style is None:
        return "Error: Por favor, elige un estilo de corte antes de continuar.", "N/A", None, None, None, None
    # Validar la combinación de estilo y género
    if style == "Estilo señorita popular" and gender == "Macho":
        return "Error: La combinación de 'Estilo señorita popular' y 'Macho' no es válida. Selecciona un estilo y género compatibles.", "N/A", None, None, None, None
    if style == "Estilo macho" and gender == "Hembra":
        return "Error: La combinación de 'Estilo macho' y 'Hembra' no es válida. Selecciona un estilo y género compatibles.", "N/A", None, None, None, None
    
    # Clasificar la imagen
    breed_description, probability = classify_image(image)
    
    # Generar imágenes solo si la predicción de la raza es válida
    if breed_description in ['Cocker', 'Pekinese', 'Poodle','Schnauzer'] and probability >= 80.99:
        generated_images = generate_image(image, breed_description, style, gender)
        return breed_description, f"Probabilidad: {probability}%", *generated_images
    else:
        return breed_description, "N/A", None, None, None, None

# Configuración de la interfaz de Gradio
iface = gr.Interface(
    fn=combined_function,
    inputs=[
        gr.Image(type='pil', label="Sube una imagen de un perro"),
        gr.Radio(
            choices=[
                "Estilo extremadamente corto",
                "Estilo señorita popular",
                "Estilo macho"
            ],
            label="Selecciona el estilo de corte"
        ),
        gr.Radio(
            choices=[
                "Hembra",
                "Macho"
            ],
            label="Selecciona el género"
        )
    ],
    outputs=[
        gr.Textbox(label="Descripción de la raza"),
        gr.Textbox(label="Probabilidad"),
        gr.Image(type='pil', label="Imagen Generada 1"),
        gr.Image(type='pil', label="Imagen Generada 2"),
        gr.Image(type='pil', label="Imagen Generada 3"),
        gr.Image(type='pil', label="Imagen Generada 4")
    ],
    title="Generador de Imágenes de Perros con Estilos de Corte",
    description=(
        "Genera imágenes de perros con estilos de corte de pelo personalizados. "
        "Sube una imagen de un perro, selecciona el estilo de corte y el género, y obtén imágenes generadas en función de la raza detectada."
    )
)

iface.launch()