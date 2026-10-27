import os
import cv2
import numpy as np

ROOT = "mesa_qwen_results"

# ref: 16 aug 2026. same frequency split for every DEM so morphology can
# be compared without changing the measurement between terrain types.
FREQ_CUTOFF = 0.05


def analyse_dem(path):
    image = cv2.imread(path, cv2.IMREAD_COLOR)

    if image is None:
        return None

    dem = image.astype(np.float32) / 255.0
    dem = dem.mean(axis=2)

    minimum = float(dem.min())
    maximum = float(dem.max())
    mean = float(dem.mean())
    std = float(dem.std())

    centred = dem - mean

    spectrum = np.fft.fft2(centred)
    power = np.abs(spectrum) ** 2

    fy = np.fft.fftfreq(dem.shape[0])
    fx = np.fft.fftfreq(dem.shape[1])
    fx, fy = np.meshgrid(fx, fy)

    radius = np.sqrt(fx ** 2 + fy ** 2)

    low_energy = power[radius <= FREQ_CUTOFF].sum()
    high_energy = power[radius > FREQ_CUTOFF].sum()
    total_energy = low_energy + high_energy

    low_pct = float(low_energy / total_energy * 100)
    high_pct = float(high_energy / total_energy * 100)

    return minimum, maximum, mean, std, low_pct, high_pct


print(
    f"{'terrain':<22}"
    f"{'min':>9}"
    f"{'max':>9}"
    f"{'mean':>9}"
    f"{'std':>9}"
    f"{'low %':>10}"
    f"{'high %':>10}"
)

print("-" * 78)

for name in sorted(os.listdir(ROOT)):
    path = os.path.join(ROOT, name, "dem.png")

    if not os.path.isfile(path):
        continue

    result = analyse_dem(path)

    if result is None:
        continue

    minimum, maximum, mean, std, low_pct, high_pct = result

    print(
        f"{name:<22}"
        f"{minimum:>9.4f}"
        f"{maximum:>9.4f}"
        f"{mean:>9.4f}"
        f"{std:>9.4f}"
        f"{low_pct:>10.2f}"
        f"{high_pct:>10.2f}"
    )