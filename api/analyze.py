import base64
import json
import os

from http.server import BaseHTTPRequestHandler
from openai import OpenAI


ALLOWED_ORIGIN = os.environ.get(
    "ALLOWED_ORIGIN",
    ""
).rstrip("/")

MAX_IMAGE_BYTES = 3 * 1024 * 1024
MAX_REQUEST_BYTES = 4_400_000
ALLOWED_PREFIXES = (
    "data:image/jpeg;base64,",
    "data:image/png;base64,",
    "data:image/webp;base64,"
)


class handler(BaseHTTPRequestHandler):

    def add_cors_headers(self):
        origin = self.headers.get("Origin", "")

        if ALLOWED_ORIGIN and origin == ALLOWED_ORIGIN:
            self.send_header(
                "Access-Control-Allow-Origin",
                origin
            )
            self.send_header("Vary", "Origin")
        elif not ALLOWED_ORIGIN:
            self.send_header("Access-Control-Allow-Origin", "*")

    def send_json(self, status_code, data):
        body = json.dumps(
            data,
            ensure_ascii=False
        ).encode("utf-8")

        self.send_response(status_code)
        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )
        self.add_cors_headers()
        self.send_header(
            "Content-Length",
            str(len(body))
        )
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.add_cors_headers()
        self.send_header(
            "Access-Control-Allow-Methods",
            "POST, OPTIONS"
        )
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type"
        )
        self.send_header(
            "Access-Control-Max-Age",
            "86400"
        )
        self.end_headers()

    def do_GET(self):
        self.send_json(
            405,
            {
                "error":
                    "Este endpoint solamente acepta POST."
            }
        )

    def do_POST(self):
        try:
            origin = self.headers.get("Origin", "")

            if ALLOWED_ORIGIN and origin != ALLOWED_ORIGIN:
                self.send_json(
                    403,
                    {"error": "Origen no autorizado."}
                )
                return

            content_length = int(
                self.headers.get("Content-Length", 0)
            )

            if (
                content_length <= 0
                or content_length > MAX_REQUEST_BYTES
            ):
                self.send_json(
                    413,
                    {"error": "La petición es demasiado grande."}
                )
                return

            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))

            image_data = str(
                data.get("image_data", "")
            ).strip()

            prompt = str(
                data.get("prompt", "")
            ).strip()

            if not image_data.startswith(ALLOWED_PREFIXES):
                self.send_json(
                    400,
                    {"error": "Formato de imagen no permitido."}
                )
                return

            try:
                encoded = image_data.split(",", 1)[1]
                image_bytes = base64.b64decode(
                    encoded,
                    validate=True
                )
            except Exception:
                self.send_json(
                    400,
                    {"error": "La imagen no contiene Base64 válido."}
                )
                return

            if (
                len(image_bytes) == 0
                or len(image_bytes) > MAX_IMAGE_BYTES
            ):
                self.send_json(
                    413,
                    {"error": "La imagen debe pesar como máximo 3 MB."}
                )
                return

            if not prompt:
                prompt = (
                    "Identifica los patrones y objetos visibles, "
                    "agrúpalos por tipo y estima cuántos aparecen."
                )

            api_key = os.environ.get("OPENAI_API_KEY")

            if not api_key:
                self.send_json(
                    500,
                    {"error": "OPENAI_API_KEY no está configurada."}
                )
                return

            client = OpenAI(api_key=api_key.strip())

            # Responses API oficial de OpenAI (Actividad 1.3)
            response = client.responses.create(
                model="gpt-5.6-luna",
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
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
                                "type": "input_image",
                                "image_url": image_data,
                                "detail": "high"
                            }
                        ]
                    }
                ],
                reasoning={
                    "effort": "none"
                },
                max_output_tokens=700
            )

            # Obtener el texto generado por la Responses API
            analysis_text = getattr(response, "output_text", None)
            if not analysis_text and hasattr(response, "output"):
                analysis_text = str(response.output)

            self.send_json(
                200,
                {
                    "analysis": analysis_text
                }
            )

        except json.JSONDecodeError:
            self.send_json(
                400,
                {"error": "El cuerpo no contiene JSON válido."}
            )

        except Exception as error:
            error_msg = str(error)
            print(f"Error en /api/analyze: {type(error).__name__}: {error_msg}")

            self.send_json(
                500,
                {
                    "error": f"Error al procesar la imagen: {error_msg}"
                }
            )