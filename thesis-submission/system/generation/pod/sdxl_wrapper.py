import io, os
import torch
from flask import Flask, request, send_file
from diffusers import AutoPipelineForText2Image

MODEL_ID = "stabilityai/sdxl-turbo"
STEPS = 4
GUIDANCE = 0.0
SIZE = 512

print("loading sdxl turbo...")
pipe = AutoPipelineForText2Image.from_pretrained(
    MODEL_ID, torch_dtype=torch.float16, variant="fp16"
)
pipe = pipe.to("cuda")
print("model resident. ready.")

app = Flask(__name__)

@app.route("/health")
def health():
    return {"status": "ok"}

@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True)
    prompt = data["prompt"]  # shaped prompt passed through as-is, no fixed prefix/suffix
    image = pipe(
        prompt=prompt,
        num_inference_steps=STEPS,
        guidance_scale=GUIDANCE,
        height=SIZE,
        width=SIZE,
    ).images[0]
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7862)