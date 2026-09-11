const API_URL = "https://patrones-five.vercel.app/api/analyze";

const form = document.getElementById("analyzeForm");
const fileInput = document.getElementById("imageInput");
const promptInput = document.getElementById("promptInput");
const preview = document.getElementById("preview");
const analyzeButton = document.getElementById("analyzeButton");
const result = document.getElementById("result");
const statusText = document.getElementById("statusText");

const MAX_FILE_SIZE = 3 * 1024 * 1024;
const ALLOWED_TYPES = [
    "image/jpeg",
    "image/png",
    "image/webp"
];

let imageData = "";

fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];

    imageData = "";
    preview.removeAttribute("src");
    analyzeButton.disabled = true;
    result.textContent = "Selecciona una imagen para comenzar.";

    if (!file) {
        return;
    }

    if (!ALLOWED_TYPES.includes(file.type)) {
        result.textContent = "Formato no permitido. Usa JPG, PNG o WebP.";
        fileInput.value = "";
        return;
    }

    if (file.size > MAX_FILE_SIZE) {
        result.textContent = "La imagen debe pesar como máximo 3 MB.";
        fileInput.value = "";
        return;
    }

    const reader = new FileReader();

    reader.onload = (event) => {
        const img = new Image();
        img.src = event.target.result;
        img.onload = () => {
            const canvas = document.createElement("canvas");
            const MAX_WIDTH = 1024;
            const MAX_HEIGHT = 1024;
            let width = img.width;
            let height = img.height;

            if (width > height) {
                if (width > MAX_WIDTH) {
                    height *= MAX_WIDTH / width;
                    width = MAX_WIDTH;
                }
            } else {
                if (height > MAX_HEIGHT) {
                    width *= MAX_HEIGHT / height;
                    height = MAX_HEIGHT;
                }
            }

            canvas.width = width;
            canvas.height = height;
            const ctx = canvas.getContext("2d");
            ctx.drawImage(img, 0, 0, width, height);

            imageData = canvas.toDataURL("image/jpeg", 0.85);
            preview.src = imageData;
            analyzeButton.disabled = false;
            result.textContent = "Imagen lista para analizar.";
        };
    };

    reader.readAsDataURL(file);
});

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!imageData) {
        result.textContent = "Primero selecciona una imagen.";
        return;
    }

    analyzeButton.disabled = true;
    statusText.textContent = "● Analizando...";
    result.textContent = "La IA está analizando los patrones visuales...";

    try {
        const response = await fetch(API_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                image_data: imageData,
                prompt: promptInput.value.trim()
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "Error del servidor"
            );
        }

        result.textContent = data.analysis;
        statusText.textContent = "● Análisis terminado";
    }
    catch (error) {
        result.textContent = "Error: " + error.message;
        statusText.textContent = "● Error";
    }
    finally {
        analyzeButton.disabled = false;
    }
});