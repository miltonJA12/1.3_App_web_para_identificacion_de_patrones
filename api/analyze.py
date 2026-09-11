import base64
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from openai import OpenAI

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
        return self.headers.get("Origin", "")

    def is_origin_allowed(self, origin):
        if not ALLOWED_ORIGIN:
            return True
        return origin.rstrip("/").lower() == ALLOWED_ORIGIN

    def add_cors_headers(self):
        origin = self.get_origin()
        if self.is_origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin if origin else "*")
            self.send_header("Vary", "Origin")

    def send_json(self, status_code, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.add_cors_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        origin = self.get_origin()
        self.send_response(204)
        if self.is_origin_allowed(origin):
            self.add_cors_headers()
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self):
        self.send_json(405, {"error": "Este endpoint solamente acepta POST."})

    def do_POST(self):
        try:
            origin = self.get_origin()

            if not self.is_origin_allowed(origin):
                self.send_json(403, {"error": "Origen no autorizado."})
                return

            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
                self.send_json(413, {"error": "La petición es demasiado grande."})
                return

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

            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                self.send_json(500, {"error": "OPENAI_API_KEY no está configurada en las variables de entorno de Vercel."})
                return

            client = OpenAI(
                api_key=api_key.strip(),
                timeout=35.0,
                max_retries=2
            )

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Analiza la imagen de forma estructurada en español:\n1. Descripción general.\n2. Patrones u objetos identificados.\n3. Conteo estimado por categoría.\n4. Nivel de certeza.\n\nSolicitud del usuario: {prompt}"
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
                max_tokens=600
            )

            reply_text = response.choices[0].message.content
            self.send_json(200, {"analysis": reply_text})

        except json.JSONDecodeError:
            self.send_json(400, {"error": "El cuerpo no contiene JSON válido."})

        except Exception as error:
            error_str = str(error)
            print(f"Error detectado en /api/analyze: {error_str}", file=sys.stderr)
            self.send_json(500, {"error": f"Error de OpenAI o Servidor: {error_str}"})