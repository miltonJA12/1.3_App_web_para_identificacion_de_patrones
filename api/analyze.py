import base64
import json
import os
from http.server import BaseHTTPRequestHandler
from openai import OpenAI

# Obtiene el origen permitido desde las variables de entorno de Vercel
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "").rstrip("/").lower()

MAX_IMAGE_BYTES = 3 * 1024 * 1024
MAX_REQUEST_BYTES = 4_400_000
ALLOWED_PREFIXES = (
    "data:image/jpeg;base64,",
    "data:image/png;base64,",
    "data:image/webp;base64,"
)

class handler(BaseHTTPRequestHandler):

    def get_origin(self):
        """Recupera la cabecera Origin enviada por el navegador."""
        return self.headers.get("Origin", "")

    def is_origin_allowed(self, origin):
        """Verifica si el origen solicitante coincide con ALLOWED_ORIGIN."""
        if not ALLOWED_ORIGIN:
            return True
        return origin.rstrip("/").lower() == ALLOWED_ORIGIN

    def add_cors_headers(self):
        """Añade cabeceras CORS para permitir la comunicación desde GitHub Pages."""
        origin = self.get_origin()
        if self.is_origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin if origin else "*")
            self.send_header("Vary", "Origin")

    def send_json(self, status_code, data):
        """Helper para responder en formato JSON estructurado."""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.add_cors_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        """Responde a las peticiones CORS pre-flight enviadas por los navegadores."""
        origin = self.get_origin()
        self.send_response(204)
        if self.is_origin_allowed(origin):
            self.add_cors_headers()
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self):
        """Rechaza peticiones GET indicando el método correcto."""
        self.send_json(405, {"error": "Este endpoint solamente acepta POST."})

    def do_POST(self):
        """Procesa las peticiones con imágenes e instrucciones hacia la API de OpenAI."""
        try:
            origin = self.get_origin()

            # 1. Validación de CORS
            if not self.is_origin_allowed(origin):
                self.send_json(403, {"error": "Origen no autorizado."})
                return

            # 2. Validación de longitud del cuerpo (permite imágenes en Base64)
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
                self.send_json(413, {"error": "La petición es demasiado grande."})
                return

            # 3. Lectura de datos
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))

            image_data = str(data.get("image_data", "")).strip()
            prompt = str(data.get("prompt", "")).strip()

            if not image_data.startswith(ALLOWED_PREFIXES):
                self.send_json(400, {"error": "Formato de imagen no permitido. Usa JPG, PNG o WebP."})
                return

            try:
                encoded = image_data.split(",", 1)[1]
                image_bytes = base64.b64decode(encoded, validate=True)
            except Exception:
                self.send_json(400, {"error": "La imagen no contiene Base64 válido."})
                return

            if len(image_bytes) == 0 or len(image_bytes) > MAX_IMAGE_BYTES:
                self.send_json(413, {"error": "La imagen debe pesar como máximo 3 MB."})
                return

            if not prompt:
                prompt = "Identifica los patrones y objetos visibles, agrúpalos por tipo y estima cuántos aparecen."

            # 4. Verificación de la API Key
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                self.send_json(500, {"error": "OPENAI_API_KEY no está configurada."})
                return

            # 5. Inicialización del cliente de OpenAI
            client = OpenAI(
                api_key=api_key.strip(),
                timeout=35.0,
                max_retries=2
            )

            # 6. Llamada Multimodal a OpenAI
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"""
Analiza la imagen como un sistema educativo de visión por computadora.
Solicitud del usuario: {prompt}

Responde en español y utiliza esta estructura:
1. Descripción general.
2. Patrones u objetos identificados.
3. Conteo estimado por categoría.
4. Evidencia visual utilizada para la identificación.
5. Nivel de certeza: alto, medio o bajo.

Si el conteo no puede determinarse con seguridad, indícalo como aproximado.
No inventes objetos que no sean visibles.
"""
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_data
                                }
                            }
                        ]
                    }
                ],
                max_tokens=700
            )

            reply_text = response.choices[0].message.content

            # 7. Respuesta exitosa
            self.send_json(200, {"analysis": reply_text})

        except json.JSONDecodeError:
            self.send_json(400, {"error": "El cuerpo no contiene JSON válido."})

        except Exception as error:
            print(f"Error en /api/analyze: {type(error).__name__}: {error}")
            self.send_json(500, {"error": f"Error en el servidor: {str(error)}"})