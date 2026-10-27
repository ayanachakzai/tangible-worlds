import os
import cv2
import numpy as np

ROOT = "mesa_qwen_results"

TERRAINS = [
    "quetta",
    "gilgit",
    "salt_plain",
    "sahara",
    "canyon",
    "grassland",
    "coastal_cliffs",
    "glacial_valley",
    "volcanic_plateau",
    "green_hills",
]


def gradient_roughness(path):
    image = cv2.imread(path, cv2.IMREAD_COLOR)

    dem = image.astype(np.float32) / 255.0
    dem = dem.mean(axis=2)

    std = dem.std()

    gy, gx = np.gradient(dem)
    gradient = np.sqrt(gx ** 2 + gy ** 2)

    # ref: 16 aug 2026. divide by dem std so multiplying the whole
    # heightfield by a different render scale does not change this score.
    roughness = gradient.mean() / std

    return float(std), float(gradient.mean()), float(roughness)


print(
    f"{'terrain':<22}"
    f"{'std':>10}"
    f"{'mean grad':>14}"
    f"{'roughness':>14}"
)

print("-" * 60)

for name in TERRAINS:
    path = os.path.join(ROOT, name, "dem.png")

    if not os.path.isfile(path):
        print(f"{name:<22} missing")
        continue

    std, mean_gradient, roughness = gradient_roughness(path)

    print(
        f"{name:<22}"
        f"{std:>10.4f}"
        f"{mean_gradient:>14.6f}"
        f"{roughness:>14.6f}"
    )