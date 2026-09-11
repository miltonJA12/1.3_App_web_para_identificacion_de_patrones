const API_URL = "https://patrones-five.vercel.app/api/analyze";

const form = document.getElementById("analyzeForm");
const fileInput = document.getElementById("imageInput");
const promptInput = document.getElementById("promptInput");
const preview = document.getElementById("preview");
const analyzeButton = document.getElementById("analyzeButton");
const result = document.getElementById("result");
const statusText = document.getElementById("statusText");

const MAX_FILE_SIZE = 3 * 1024 * 1024; // 3 MB
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

    reader.onload = () => {
        imageData = reader.result;
        preview.src = imageData;
        analyzeButton.disabled = false;
        result.textContent = "Imagen lista para analizar.";
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