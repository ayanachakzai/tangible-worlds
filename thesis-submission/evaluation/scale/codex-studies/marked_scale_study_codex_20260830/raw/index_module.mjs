import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { Sky } from 'three/addons/objects/Sky.js';
import { ImprovedNoise } from 'three/addons/math/ImprovedNoise.js';

// ref: https://github.com/mrdoob/three.js/blob/r170/examples/jsm/controls/OrbitControls.js
// ref: https://github.com/mrdoob/three.js/blob/r170/examples/jsm/loaders/GLTFLoader.js
// ref: https://github.com/mrdoob/three.js/blob/r170/examples/jsm/objects/Sky.js
// ref: https://github.com/mrdoob/three.js/blob/r170/examples/jsm/math/ImprovedNoise.js

// ── Settings ───────────────────────────────────────────

const SCENE_POLL_MS = 200;       // object position poll rate
const MODIFIER_POLL_MS = 500;    // atmosphere modifier poll rate
const CALIBRATION_POLL_MS = 250; // fast enough to catch a status change promptly during a ~4.5s scan
const TABLE_SIZE = 10;
const OBJECT_HEIGHT = 0.6;

// atmosphere defaults match the final 12-field schema in serve.py/converse.py.
// numeric defaults and low-level renderer mappings are project tuning from
// iterative visual tests.
const FIXED_TABLE_COLOR = 0x777777;
const DEFAULT_MODIFIERS = {
    sky_elevation: 45,
    light_elevation: 45,
    light_azimuth: 45,
    light_level: 0.65,
    light_warmth: 0,
    sky_haze: 0.2,
    mist_amount: 0,
    mist_height: 0.35,
    mist_motion: 0.25,
    rain_amount: 0,
    lightning_amount: 0,
    mood: 'neutral',
};


// ── Scene setup ────────────────────────────────────────

const scene = new THREE.Scene();

// Camera: looking down at the table, slightly angled.
const camera = new THREE.PerspectiveCamera(
    50, window.innerWidth / window.innerHeight, 0.1, 100
);
camera.position.set(0, 12, 5);
camera.lookAt(0, 0, 0);

// ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/renderers/WebGLRenderer.html
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
document.body.appendChild(renderer.domElement);

// ref: https://github.com/mrdoob/three.js/blob/r170/examples/jsm/controls/OrbitControls.js
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

// ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/lights/DirectionalLight.html
// project mapping: elevation and azimuth place one shadow-casting key light
// around the tabletop. Distance only keeps the light outside the table bounds.
const dirLight = new THREE.DirectionalLight(0xffffff, 1.0);
dirLight.castShadow = true;
dirLight.shadow.camera.left = -TABLE_SIZE;
dirLight.shadow.camera.right = TABLE_SIZE;
dirLight.shadow.camera.top = TABLE_SIZE;
dirLight.shadow.camera.bottom = -TABLE_SIZE;
dirLight.shadow.camera.near = 0.5;
dirLight.shadow.camera.far = 50;
dirLight.shadow.mapSize.set(2048, 2048);
dirLight.shadow.bias = -0.001;
scene.add(dirLight);

function setLightAngle(elevationDeg, azimuthDeg) {
    const dist = TABLE_SIZE * 3;
    const el = THREE.MathUtils.degToRad(elevationDeg);
    const az = THREE.MathUtils.degToRad(azimuthDeg);
    dirLight.position.set(
        dist * Math.cos(el) * Math.cos(az),
        dist * Math.sin(el),
        dist * Math.cos(el) * Math.sin(az)
    );
}

// The ground material never changes with mood. Atmosphere changes sky, light
// and air instead. Colour and roughness are project tuning from visual tests.
// ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/materials/MeshStandardMaterial.html
const tableGeo = new THREE.PlaneGeometry(TABLE_SIZE, TABLE_SIZE);
const tableMat = new THREE.MeshStandardMaterial({
    color: FIXED_TABLE_COLOR,
    roughness: 0.8,
});
const tableMesh = new THREE.Mesh(tableGeo, tableMat);
tableMesh.rotation.x = -Math.PI / 2;
tableMesh.receiveShadow = true;
scene.add(tableMesh);

// Grid colours are project tuning from iterative visual tests.
const grid = new THREE.GridHelper(TABLE_SIZE, 10, 0x46515a, 0x364049);
grid.position.y = 0.012;
scene.add(grid);

// Procedural sky. No HDRI or downloaded environment asset is used.
// ref: https://github.com/mrdoob/three.js/blob/r170/examples/jsm/objects/Sky.js
// ref: https://github.com/mrdoob/three.js/blob/r170/examples/webgl_shaders_ocean.html
// ref: https://doi.org/10.1145/311535.311545
// ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/extras/PMREMGenerator.html
const sky = new Sky();
sky.scale.setScalar(450000);
const skyUniforms = sky.material.uniforms;
const skySun = new THREE.Vector3();
const environmentScene = new THREE.Scene();
const pmrem = new THREE.PMREMGenerator(renderer);
let environmentTarget = null;

environmentScene.add(sky);

function setSkySun(elevationDeg, azimuthDeg = 180) {
    const phi = THREE.MathUtils.degToRad(90 - elevationDeg);
    const theta = THREE.MathUtils.degToRad(azimuthDeg);
    skySun.setFromSphericalCoords(1, phi, theta);
    skyUniforms.sunPosition.value.copy(skySun);
}

function refreshEnvironment() {
    if (sky.parent !== environmentScene) environmentScene.add(sky);
    const nextTarget = pmrem.fromScene(environmentScene);
    if (environmentTarget) environmentTarget.dispose();
    environmentTarget = nextTarget;
    scene.environment = environmentTarget.texture;
    if (sky.parent !== scene) scene.add(sky);
}

function smoothstep(edge0, edge1, value) {
    const x = THREE.MathUtils.clamp((value - edge0) / (edge1 - edge0), 0, 1);
    return x * x * (3 - 2 * x);
}

// Layered world-space mist. Several horizontal alpha slices approximate
// a shallow volume while staying fixed in world space.
// ref: https://developer.nvidia.com/gpugems/gpugems/part-vi-beyond-triangles/chapter-39-volume-rendering-techniques
// ref: https://github.com/mrdoob/three.js/blob/r170/examples/jsm/math/ImprovedNoise.js
// ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/textures/CanvasTexture.html
function makeMistTexture(seed) {
    const size = 256;
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = size;
    const ctx = canvas.getContext('2d');
    const image = ctx.createImageData(size, size);
    const noise = new ImprovedNoise();

    for (let y = 0; y < size; y++) {
        const v = y / (size - 1);
        for (let x = 0; x < size; x++) {
            const u = x / (size - 1);
            const px = u * 3.3;
            const py = v * 3.3;

            const coarse = (noise.noise(px, seed, py) + 1) * 0.5;
            const mid = (noise.noise(px * 1.9 + 13.2, seed + 7.1, py * 1.9 + 5.8) + 1) * 0.5;
            const fine = (noise.noise(px * 3.7 + 23.4, seed + 13.7, py * 3.7 + 17.2) + 1) * 0.5;
            const n = 0.64 * coarse + 0.26 * mid + 0.10 * fine;

            let alpha = smoothstep(0.33, 0.70, n);
            const edgeX = smoothstep(0, 0.06, u) * smoothstep(0, 0.06, 1 - u);
            const edgeY = smoothstep(0, 0.06, v) * smoothstep(0, 0.06, 1 - v);
            alpha *= edgeX * edgeY;

            const i = (y * size + x) * 4;
            const value = Math.round(alpha * 255);
            image.data[i] = value;
            image.data[i + 1] = value;
            image.data[i + 2] = value;
            image.data[i + 3] = 255;
        }
    }

    ctx.putImageData(image, 0, 0);
    const texture = new THREE.CanvasTexture(canvas);
    texture.minFilter = THREE.LinearFilter;
    texture.magFilter = THREE.LinearFilter;
    return texture;
}

const mistSources = [makeMistTexture(0), makeMistTexture(17), makeMistTexture(41)];

// ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/materials/MeshStandardMaterial.html
// ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/textures/Texture.html
// project tuning: layer heights, opacity, sizes and motion values come from
// iterative visual tests.
const mistConfigs = [
    {
        y: 0.12, wobble: 0.02, size: 20,
        opacityA: 0.072, opacityB: 0.055, sourceA: 0, sourceB: 1,
        speedAX: 0.018, speedAZ: 0.007, speedBX: -0.009, speedBZ: 0.014,
        rotA: 0.0035, rotB: -0.0025, phase: 0.0,
    },
    {
        y: 0.25, wobble: 0.024, size: 19,
        opacityA: 0.065, opacityB: 0.050, sourceA: 1, sourceB: 2,
        speedAX: -0.015, speedAZ: 0.011, speedBX: 0.011, speedBZ: -0.009,
        rotA: -0.0025, rotB: 0.0035, phase: 0.8,
    },
    {
        y: 0.42, wobble: 0.03, size: 18,
        opacityA: 0.058, opacityB: 0.045, sourceA: 2, sourceB: 0,
        speedAX: 0.013, speedAZ: -0.011, speedBX: -0.007, speedBZ: 0.012,
        rotA: 0.0025, rotB: -0.002, phase: 1.7,
    },
    {
        y: 0.64, wobble: 0.035, size: 17,
        opacityA: 0.052, opacityB: 0.040, sourceA: 0, sourceB: 2,
        speedAX: -0.011, speedAZ: -0.008, speedBX: 0.008, speedBZ: 0.010,
        rotA: -0.002, rotB: 0.003, phase: 2.5,
    },
    {
        y: 0.90, wobble: 0.04, size: 16,
        opacityA: 0.045, opacityB: 0.034, sourceA: 1, sourceB: 0,
        speedAX: 0.009, speedAZ: 0.009, speedBX: -0.006, speedBZ: -0.007,
        rotA: 0.0018, rotB: -0.0026, phase: 3.2,
    },
    {
        y: 1.18, wobble: 0.045, size: 15,
        opacityA: 0.038, opacityB: 0.029, sourceA: 2, sourceB: 1,
        speedAX: -0.007, speedAZ: 0.006, speedBX: 0.005, speedBZ: -0.005,
        rotA: -0.0018, rotB: 0.0022, phase: 3.9,
    },
];

function makeMistLayer(alphaMap, opacity, size, tint) {
    const material = new THREE.MeshStandardMaterial({
        color: tint,
        roughness: 1,
        metalness: 0,
        transparent: true,
        opacity,
        alphaMap,
        depthWrite: false,
        side: THREE.DoubleSide,
    });
    const layer = new THREE.Mesh(new THREE.PlaneGeometry(size, size), material);
    layer.rotation.x = -Math.PI / 2;
    return layer;
}

const mistGroups = mistConfigs.map((config) => {
    const group = new THREE.Group();
    const alphaA = mistSources[config.sourceA].clone();
    alphaA.wrapS = alphaA.wrapT = THREE.RepeatWrapping;
    alphaA.needsUpdate = true;

    const alphaB = mistSources[config.sourceB].clone();
    alphaB.wrapS = alphaB.wrapT = THREE.RepeatWrapping;
    alphaB.needsUpdate = true;

    const layerA = makeMistLayer(alphaA, config.opacityA, config.size, 0xb9c6d6);
    const layerB = makeMistLayer(alphaB, config.opacityB, config.size * 0.96, 0xc7d2df);
    layerB.position.y = 0.01;
    layerB.rotation.z = Math.PI * 0.18;

    group.userData = { config, layerA, layerB };
    group.add(layerA);
    group.add(layerB);
    scene.add(group);
    return group;
});

function wrapOffset(value) {
    return ((value % 1) + 1) % 1;
}

function applyMistAtTime(timeSeconds, amount, height, motion) {
    const baseMinY = 0.08;
    const baseMaxY = 1.35;
    const extraHeight = height * 0.9;
    const motionScale = 0.35 + motion * 1.35;

    for (const group of mistGroups) {
        const { config, layerA, layerB } = group.userData;
        const normalizedY = (config.y - 0.12) / (1.18 - 0.12);
        const targetY = THREE.MathUtils.lerp(baseMinY, baseMaxY + extraHeight, normalizedY);
        const wobble = config.wobble * motionScale;

        group.visible = amount > 0.01;
        group.position.y = targetY + Math.sin(timeSeconds * 0.22 * motionScale + config.phase) * wobble;
        layerA.rotation.z = timeSeconds * config.rotA * motionScale;
        layerB.rotation.z = Math.PI * 0.18 + timeSeconds * config.rotB * motionScale;
        layerA.material.alphaMap.offset.set(
            wrapOffset(timeSeconds * config.speedAX * motionScale),
            wrapOffset(timeSeconds * config.speedAZ * motionScale)
        );
        layerB.material.alphaMap.offset.set(
            wrapOffset(timeSeconds * config.speedBX * motionScale),
            wrapOffset(timeSeconds * config.speedBZ * motionScale)
        );
        layerA.material.opacity = config.opacityA * amount;
        layerB.material.opacity = config.opacityB * amount;
    }
}

// World-space rain uses one short LineSegments pair per drop. Count, spread,
// length and speed are project tuning from iterative visual tests.
// ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/core/BufferGeometry.html
// ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/core/BufferAttribute.html
// ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/objects/LineSegments.html
// ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/materials/LineBasicMaterial.html
const RAIN_COUNT = 450;
const rainBase = Array.from({ length: RAIN_COUNT }, (_, i) => {
    const x = ((((i * 73) % 1000) / 1000) - 0.5) * TABLE_SIZE * 1.35;
    const z = ((((i * 37 + 211) % 1000) / 1000) - 0.5) * TABLE_SIZE * 1.35;
    const y0 = 0.4 + ((((i * 91 + 17) % 1000) / 1000) * 8.5);
    const speed = 5.2 + ((((i * 53 + 101) % 1000) / 1000) * 2.8);
    const length = 0.16 + ((((i * 29 + 401) % 1000) / 1000) * 0.20);
    return { x, z, y0, speed, length };
});
const rainPositions = new Float32Array(RAIN_COUNT * 2 * 3);
const rainGeometry = new THREE.BufferGeometry();
const rainPositionAttribute = new THREE.BufferAttribute(rainPositions, 3);
rainPositionAttribute.setUsage(THREE.DynamicDrawUsage);
rainGeometry.setAttribute('position', rainPositionAttribute);
const rainMaterial = new THREE.LineBasicMaterial({
    color: 0xa9bed0,
    transparent: true,
    opacity: 0,
    depthWrite: false,
});
const rain = new THREE.LineSegments(rainGeometry, rainMaterial);
rain.renderOrder = 30;
scene.add(rain);

function applyRainAtTime(timeSeconds, amount) {
    const visibleCount = Math.round(RAIN_COUNT * amount);
    for (let i = 0; i < RAIN_COUNT; i++) {
        const off = i * 6;
        if (i >= visibleCount) {
            rainPositions[off] = rainPositions[off + 1] = rainPositions[off + 2] = 0;
            rainPositions[off + 3] = rainPositions[off + 4] = rainPositions[off + 5] = 0;
            continue;
        }
        const base = rainBase[i];
        const span = 9.6;
        const cycleY = (base.y0 - timeSeconds * base.speed) % span;
        const y = cycleY < 0 ? cycleY + span : cycleY;
        rainPositions[off] = base.x;
        rainPositions[off + 1] = y;
        rainPositions[off + 2] = base.z;
        rainPositions[off + 3] = base.x - 0.05;
        rainPositions[off + 4] = y - base.length;
        rainPositions[off + 5] = base.z + 0.025;
    }
    rainPositionAttribute.needsUpdate = true;
}

// ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/math/Color.html
function lerpColorHex(a, b, t) {
    return new THREE.Color(a).lerp(new THREE.Color(b), t);
}

function clampModifiers(raw) {
    return {
        sky_elevation: THREE.MathUtils.clamp(Number(raw.sky_elevation ?? 45), -12, 90),
        light_elevation: THREE.MathUtils.clamp(Number(raw.light_elevation ?? 45), 0, 90),
        light_azimuth: ((Number(raw.light_azimuth ?? 45) % 360) + 360) % 360,
        light_level: THREE.MathUtils.clamp(Number(raw.light_level ?? 0.65), 0, 1),
        light_warmth: THREE.MathUtils.clamp(Number(raw.light_warmth ?? 0), -1, 1),
        sky_haze: THREE.MathUtils.clamp(Number(raw.sky_haze ?? 0.2), 0, 1),
        mist_amount: THREE.MathUtils.clamp(Number(raw.mist_amount ?? 0), 0, 1),
        mist_height: THREE.MathUtils.clamp(Number(raw.mist_height ?? 0.35), 0, 1),
        mist_motion: THREE.MathUtils.clamp(Number(raw.mist_motion ?? 0.25), 0, 1),
        rain_amount: THREE.MathUtils.clamp(Number(raw.rain_amount ?? 0), 0, 1),
        lightning_amount: THREE.MathUtils.clamp(Number(raw.lightning_amount ?? 0), 0, 1),
        mood: String(raw.mood ?? 'neutral'),
    };
}

let activeModifiers = clampModifiers(DEFAULT_MODIFIERS);
let baseLightIntensity = 1;
let baseExposure = 0.6;
let nextFlashAt = 3.5;
let flashStartedAt = null;

function resetLightningClock(nowSeconds = performance.now() * 0.001) {
    nextFlashAt = nowSeconds + 3.5;
    flashStartedAt = null;
}

// Lightning uses an irregular two-pulse light/exposure flash.
// Pulse timings and strengths are project tuning from visual tests.
// ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/lights/DirectionalLight.html
// ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/renderers/WebGLRenderer.html
function lightningStrength(timeSeconds) {
    if (flashStartedAt === null) {
        if (timeSeconds >= nextFlashAt) flashStartedAt = timeSeconds;
        else return 0;
    }
    const t = timeSeconds - flashStartedAt;
    if (t < 0.055) return t / 0.055;
    if (t < 0.115) return 1.0 - (t - 0.055) / 0.060 * 0.82;
    if (t < 0.180) return 0.18 + (t - 0.115) / 0.065 * 0.62;
    if (t < 0.340) return 0.80 * (1.0 - (t - 0.180) / 0.160);
    flashStartedAt = null;
    nextFlashAt = timeSeconds + 7.0;
    return 0;
}

function applyAtmosphere(mods, forceEnvironment = false) {
    const next = clampModifiers({ ...activeModifiers, ...mods });
    const oldSkyElevation = activeModifiers.sky_elevation;
    const oldSkyHaze = activeModifiers.sky_haze;
    const oldLightning = activeModifiers.lightning_amount;
    activeModifiers = next;

    // sky_elevation: procedural sky sun height, range -12..90.
    // ref: https://github.com/mrdoob/three.js/blob/r170/examples/jsm/objects/Sky.js
    setSkySun(next.sky_elevation, 180);

    // light_elevation + light_azimuth: key-light direction and shadow angle.
    // ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/lights/DirectionalLight.html
    setLightAngle(next.light_elevation, next.light_azimuth);

    // light_level: semantic 0..1 mapped to a readable directional intensity.
    // mapping is project tuning from iterative visual tests.
    baseLightIntensity = THREE.MathUtils.lerp(0.45, 6.0, Math.pow(next.light_level, 1.15));

    // light_warmth: -1 cool, 0 neutral, 1 warm.
    // ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/math/Color.html
    const lightWarmT = (next.light_warmth + 1) * 0.5;
    const keyColor = lightWarmT < 0.5
        ? lerpColorHex(0xbcd1f0, 0xffffff, lightWarmT / 0.5)
        : lerpColorHex(0xffffff, 0xff9f5f, (lightWarmT - 0.5) / 0.5);
    dirLight.color.copy(keyColor);
    dirLight.intensity = baseLightIntensity;

    // sky_haze: 0..1 mapped to the Sky scattering uniforms.
    // ref: https://github.com/mrdoob/three.js/blob/r170/examples/jsm/objects/Sky.js
    skyUniforms.turbidity.value = THREE.MathUtils.lerp(2.0, 12.0, next.sky_haze);
    skyUniforms.rayleigh.value = THREE.MathUtils.lerp(1.8, 0.45, next.sky_haze);
    skyUniforms.mieCoefficient.value = THREE.MathUtils.lerp(0.002, 0.010, next.sky_haze);
    skyUniforms.mieDirectionalG.value = THREE.MathUtils.lerp(0.80, 0.90, next.sky_haze);

    // The PMREM only needs rebuilding when sky elevation or haze changes.
    if (forceEnvironment || next.sky_elevation !== oldSkyElevation || next.sky_haze !== oldSkyHaze) {
        refreshEnvironment();
    }

    // ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/scenes/Scene.html
    // mapping is project tuning from iterative visual tests.
    scene.environmentIntensity = THREE.MathUtils.lerp(2.4, 0.25, next.light_level);

    // ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/renderers/WebGLRenderer.html
    baseExposure = THREE.MathUtils.lerp(0.78, 0.48, next.light_level);
    renderer.toneMappingExposure = baseExposure;

    if (oldLightning <= 0.01 && next.lightning_amount > 0.01) resetLightningClock();
    if (next.lightning_amount <= 0.01) flashStartedAt = null;

    const moodEl = document.getElementById('mood-display');
    moodEl.textContent = next.mood && next.mood !== 'neutral'
        ? `Mood: ${next.mood}`
        : '';
}

function updateAtmosphere(timeSeconds) {
    // Mist remains horizontal in world space and morphs through texture drift.
    applyMistAtTime(
        timeSeconds,
        activeModifiers.mist_amount,
        activeModifiers.mist_height,
        activeModifiers.mist_motion
    );

    rain.visible = activeModifiers.rain_amount > 0.01;
    if (rain.visible) applyRainAtTime(timeSeconds, activeModifiers.rain_amount);

    const flash = activeModifiers.lightning_amount > 0.01
        ? lightningStrength(timeSeconds) * activeModifiers.lightning_amount
        : 0;
    dirLight.intensity = baseLightIntensity + flash * (3.0 + activeModifiers.lightning_amount * 5.0);
    renderer.toneMappingExposure = baseExposure + flash * 0.30;
    rainMaterial.opacity = activeModifiers.rain_amount * (0.30 + flash * 0.18);
}

// Apply the neutral schema defaults before the first modifier poll.
applyAtmosphere(DEFAULT_MODIFIERS, true);


// ── Calibration scan animation ─────────────────────────
//
// Participant-triggered calibration visual. The tracker performs the
// measurement; this animation waits for /api/calibration to confirm completion.

const CALIB_GRID_N = 28;
const CALIB_MAX_HEIGHT = 0.55;
const CALIB_REST_Y = -0.3;
const CALIB_RISE_SECONDS = 0.5;
const CALIB_MIN_HOLD_SECONDS = 1.6;
const CALIB_FADE_SECONDS = 0.9;
const CALIB_TIMEOUT_MS = 20000;  // give up and show an error rather than shimmer forever

// Project-tuned thermal colour stops for the calibration visual.
const CALIB_STOPS = [
    [0.00, [0x3b, 0x0f, 0x70]],
    [0.20, [0x2a, 0x6d, 0xc9]],
    [0.40, [0x1f, 0xc3, 0xa0]],
    [0.60, [0xa8, 0xd9, 0x3f]],
    [0.80, [0xf7, 0xb3, 0x2b]],
    [1.00, [0xe0, 0x34, 0x2a]],
];
function calibThermalColor(t) {
    t = Math.max(0, Math.min(1, t));
    for (let i = 0; i < CALIB_STOPS.length - 1; i++) {
        const [t0, c0] = CALIB_STOPS[i];
        const [t1, c1] = CALIB_STOPS[i + 1];
        if (t >= t0 && t <= t1) {
            const f = (t - t0) / (t1 - t0 || 1);
            return [
                (c0[0] + (c1[0] - c0[0]) * f) / 255,
                (c0[1] + (c1[1] - c0[1]) * f) / 255,
                (c0[2] + (c1[2] - c0[2]) * f) / 255,
            ];
        }
    }
    return [1, 1, 1];
}

function calibDotTexture() {
    const size = 64;
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = size;
    const ctx = canvas.getContext('2d');
    const grad = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
    grad.addColorStop(0, 'rgba(255,255,255,1)');
    grad.addColorStop(0.4, 'rgba(255,255,255,0.85)');
    grad.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, size, size);
    return new THREE.CanvasTexture(canvas);
}

const calibCount = CALIB_GRID_N * CALIB_GRID_N;
const calibPositions = new Float32Array(calibCount * 3);
const calibColors = new Float32Array(calibCount * 3);
const calibPointState = [];

let calibIdx = 0;
for (let i = 0; i < CALIB_GRID_N; i++) {
    for (let j = 0; j < CALIB_GRID_N; j++) {
        const jitterX = (Math.random() - 0.5) * 0.25;
        const jitterZ = (Math.random() - 0.5) * 0.25;
        const x = (i / (CALIB_GRID_N - 1) - 0.5) * (TABLE_SIZE * 0.92) + jitterX;
        const z = (j / (CALIB_GRID_N - 1) - 0.5) * (TABLE_SIZE * 0.92) + jitterZ;
        const targetY = 0.05 + Math.random() * CALIB_MAX_HEIGHT;
        const distFromCenter = Math.sqrt(x * x + z * z) / (TABLE_SIZE * 0.7);
        const revealDelay = distFromCenter * 1.1 + Math.random() * 0.9;

        calibPointState.push({
            x, z, targetY, revealDelay,
            phase: Math.random() * Math.PI * 2,
            wobbleFreq: 1.2 + Math.random() * 1.4,
            wobbleAmp: 0.02 + Math.random() * 0.03,
        });

        calibPositions[calibIdx * 3] = x;
        calibPositions[calibIdx * 3 + 1] = CALIB_REST_Y;
        calibPositions[calibIdx * 3 + 2] = z;
        calibIdx++;
    }
}

const calibGeo = new THREE.BufferGeometry();
calibGeo.setAttribute('position', new THREE.BufferAttribute(calibPositions, 3));
calibGeo.setAttribute('color', new THREE.BufferAttribute(calibColors, 3));

const calibMat = new THREE.PointsMaterial({
    size: 0.16,
    map: calibDotTexture(),
    vertexColors: true,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    sizeAttenuation: true,
});
const calibCloud = new THREE.Points(calibGeo, calibMat);
calibCloud.visible = false;
scene.add(calibCloud);

function calibEase(t) { return 1 - Math.pow(1 - t, 3); }

// phase: 'idle' | 'rising' | 'holding' | 'fading'
let calibPhase = 'idle';
let calibPhaseStart = 0;
let calibVisualStart = 0;
let calibTotalRise = 0;
let calibBackendDone = false;
let calibResultText = '';

function calibResetUI(message) {
    const statusEl = document.getElementById('calibration-status');
    const btn = document.getElementById('calibrate-btn');
    statusEl.textContent = message;
    btn.textContent = 'start calibration';
    btn.disabled = false;
}

function calibStartVisual() {
    calibPhase = 'rising';
    calibPhaseStart = performance.now();
    calibVisualStart = calibPhaseStart;
    calibBackendDone = false;
    calibCloud.visible = true;
    calibMat.opacity = 1;
    const maxDelay = Math.max(...calibPointState.map(p => p.revealDelay));
    calibTotalRise = maxDelay + CALIB_RISE_SECONDS;
}

function calibUpdate(nowMs) {
    if (calibPhase === 'idle') return;

    if (!calibBackendDone && (nowMs - calibVisualStart) > CALIB_TIMEOUT_MS) {
        calibPhase = 'idle';
        calibCloud.visible = false;
        calibMat.opacity = 1;
        calibResetUI('calibration timed out, is track_tabletop.py running?');
        return;
    }

    const posAttr = calibGeo.attributes.position;
    const colAttr = calibGeo.attributes.color;

    if (calibPhase === 'rising' || calibPhase === 'holding') {
        const t = (nowMs - calibPhaseStart) / 1000;
        if (calibPhase === 'rising' && t >= calibTotalRise) {
            calibPhase = 'holding';
            calibPhaseStart = nowMs;
        }
        const holdT = calibPhase === 'holding' ? (nowMs - calibPhaseStart) / 1000 : 0;

        for (let k = 0; k < calibCount; k++) {
            const p = calibPointState[k];
            const localT = t - p.revealDelay;
            let y;
            if (localT <= 0) {
                y = CALIB_REST_Y;
            } else {
                const riseT = Math.min(localT / CALIB_RISE_SECONDS, 1);
                const risen = CALIB_REST_Y + (p.targetY - CALIB_REST_Y) * calibEase(riseT);
                const wobble = riseT >= 1 ? Math.sin((t + holdT) * p.wobbleFreq + p.phase) * p.wobbleAmp : 0;
                y = risen + wobble;
            }
            posAttr.array[k * 3 + 1] = y;
            const norm = Math.max(0, Math.min(1, (y - CALIB_REST_Y) / (CALIB_MAX_HEIGHT - CALIB_REST_Y)));
            const [r, g, b] = calibThermalColor(norm);
            colAttr.array[k * 3] = r;
            colAttr.array[k * 3 + 1] = g;
            colAttr.array[k * 3 + 2] = b;
        }
        posAttr.needsUpdate = true;
        colAttr.needsUpdate = true;

        // won't start fading until BOTH the minimum hold has played
        // AND the backend has actually confirmed a locked threshold.
        if (calibPhase === 'holding' && holdT >= CALIB_MIN_HOLD_SECONDS && calibBackendDone) {
            calibPhase = 'fading';
            calibPhaseStart = nowMs;
        }
    } else if (calibPhase === 'fading') {
        const t = (nowMs - calibPhaseStart) / 1000;
        const f = Math.min(t / CALIB_FADE_SECONDS, 1);
        calibMat.opacity = 1 - f;
        if (f >= 1) {
            calibPhase = 'idle';
            calibCloud.visible = false;
            calibMat.opacity = 1;
            for (let k = 0; k < calibCount; k++) posAttr.array[k * 3 + 1] = CALIB_REST_Y;
            posAttr.needsUpdate = true;
            calibResetUI(calibResultText);
            document.getElementById('calibrate-btn').textContent = 'recalibrate';
        }
    }
}

async function startCalibrationFlow() {
    const btn = document.getElementById('calibrate-btn');
    btn.disabled = true;
    btn.textContent = 'scanning\u2026';
    document.getElementById('calibration-status').textContent = 'calibrating table\u2026';

    calibStartVisual();

    try {
        await fetch('/api/calibrate', { method: 'POST' });
    } catch (err) {
        console.error('[calibrate] failed to trigger', err);
        calibPhase = 'idle';
        calibCloud.visible = false;
        calibResetUI('could not reach the server, check serve.py is running');
    }
}

document.getElementById('calibrate-btn').addEventListener('click', startCalibrationFlow);

async function pollCalibration() {
    try {
        const res = await fetch('/api/calibration');
        if (!res.ok) return;
        const data = await res.json();
        if (data.status === 'done' && calibPhase !== 'idle' && !calibBackendDone) {
            calibBackendDone = true;
            calibResultText = `calibrated: noise ${data.noise_mm}mm, threshold ${data.thresh_mm}mm`;
        }
    } catch {
        // network hiccup, next poll retries on its own, nothing to surface
    }
}


// ── Object + relationship management ───────────────────

const meshes = {};
const relationshipLines = [];


// ── Assignment-aware object appearance ──────────────────
//
// Physical tracking identity and assigned semantic meaning are separate.
// Once generation is ready, assignment.mesh_url replaces the placeholder
// with the generated GLB while the tracker id remains the interaction handle.

function hashColor(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    const hue = Math.abs(hash) % 360;
    return new THREE.Color(`hsl(${hue}, 55%, 55%)`);
}

function makeLabelSprite(text) {
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 64;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 24px monospace';
    ctx.textAlign = 'center';
    ctx.fillText(text, 128, 40);
    const texture = new THREE.CanvasTexture(canvas);
    const sprite = new THREE.Sprite(
        new THREE.SpriteMaterial({ map: texture, transparent: true })
    );
    sprite.position.y = OBJECT_HEIGHT + 0.3;
    sprite.scale.set(1.5, 0.4, 1);
    return sprite;
}

const gltfLoader = new GLTFLoader();
const gltfCache = {};  // mesh_url -> loaded THREE.Object3D template, cloned per use

function applyRotationAndRest(obj, rotationDeg) {
    // Generated meshes have no guaranteed canonical orientation. Reset
    // position each call so repeated rotation changes do not drift vertically.
    rotationDeg = rotationDeg || { x: 0, y: 0, z: 0 };
    obj.position.y = 0;
    obj.rotation.x = THREE.MathUtils.degToRad(rotationDeg.x || 0);
    obj.rotation.y = THREE.MathUtils.degToRad(rotationDeg.y || 0);
    obj.rotation.z = THREE.MathUtils.degToRad(rotationDeg.z || 0);
    const box = new THREE.Box3().setFromObject(obj);
    obj.position.y -= box.min.y;
}

function normalizeAndAddModel(container, sceneObj, rotationDeg, targetSize) {
    // Generated meshes arrive at unpredictable scale, so normalize them to
    // a consistent tabletop footprint. Interstitial meshes can pass a smaller size.
    targetSize = targetSize || 0.9;
    const box = new THREE.Box3().setFromObject(sceneObj);
    const size = new THREE.Vector3();
    box.getSize(size);
    const maxDim = Math.max(size.x, size.y, size.z) || 1;
    sceneObj.scale.setScalar(targetSize / maxDim);

    // GLTF meshes keep their generated material. Only shadow flags are added.
    // ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/core/Object3D.html
    sceneObj.traverse((node) => {
        if (!node.isMesh) return;
        node.castShadow = true;
        node.receiveShadow = true;
    });

    applyRotationAndRest(sceneObj, rotationDeg);
    container.add(sceneObj);
}

function syncRotation(group, rotationDeg) {
    // Called every poll. Only touches the mesh if the server-side
    // rotation actually changed, so clicking a Rotate button updates
    // the already-loaded model live, no reload needed.
    rotationDeg = rotationDeg || { x: 0, y: 0, z: 0 };
    const applied = group.userData.appliedRotation;
    if (applied && applied.x === rotationDeg.x && applied.y === rotationDeg.y && applied.z === rotationDeg.z) {
        return;
    }
    for (const child of group.children) {
        if (child.isSprite) continue;
        applyRotationAndRest(child, rotationDeg);
    }
    group.userData.appliedRotation = { x: rotationDeg.x || 0, y: rotationDeg.y || 0, z: rotationDeg.z || 0 };
}

function loadGeneratedMesh(container, meshUrl, placeholderToRemove, rotationDeg, targetSize) {
    const onLoaded = (sceneObj) => {
        if (placeholderToRemove) container.remove(placeholderToRemove);
        normalizeAndAddModel(container, sceneObj, rotationDeg, targetSize);
        container.userData.appliedRotation = {
            x: (rotationDeg && rotationDeg.x) || 0,
            y: (rotationDeg && rotationDeg.y) || 0,
            z: (rotationDeg && rotationDeg.z) || 0,
        };
    };

    if (gltfCache[meshUrl]) {
        onLoaded(gltfCache[meshUrl].clone());
        return;
    }

    gltfLoader.load(
        meshUrl,
        (gltf) => {
            gltfCache[meshUrl] = gltf.scene;
            onLoaded(gltf.scene.clone());
        },
        undefined,
        (err) => {
            console.error('[mesh] failed to load', meshUrl, err);
            // Placeholder box stays visible on failure, better than nothing.
        }
    );
}

// The numeric tracker id is the visible reference handle for assignment.
function createAssignmentMesh(id, label, assignment) {
    const kind = !assignment
        ? 'unassigned'
        : assignment.status === 'ready' ? 'ready'
        : assignment.status === 'failed' ? 'failed'
        : 'generating';

    if (kind === 'ready') {
        // A group, not a single Mesh: the real .glb loads
        // asynchronously, so a placeholder box shows immediately
        // and gets swapped out once loading finishes.
        const group = new THREE.Group();
        group.userData.kind = kind;

        const placeholder = new THREE.Mesh(
            new THREE.BoxGeometry(0.45, OBJECT_HEIGHT, 0.45),
            new THREE.MeshStandardMaterial({
                color: hashColor(assignment.meaning), roughness: 0.5, metalness: 0.1,
            })
        );
        placeholder.position.y = OBJECT_HEIGHT / 2;
        placeholder.castShadow = true;
        group.add(placeholder);

        if (assignment.mesh_url) {
            // Old records predate participant scale and therefore stay neutral.
            // ref: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Number/isFinite
            const targetSize = Number.isFinite(assignment.target_size)
                ? assignment.target_size
                : 1.0;
            loadGeneratedMesh(group, assignment.mesh_url, placeholder, assignment.rotation, targetSize);
        }

        group.add(makeLabelSprite(assignment.meaning));
        return group;
    }

    let geo, mat, labelText;
    if (kind === 'failed') {
        geo = new THREE.SphereGeometry(0.22, 12, 12);
        mat = new THREE.MeshStandardMaterial({ color: 0xaa3333, roughness: 0.9 });
        labelText = `${id} (failed, see terminal)`;
    } else if (kind === 'generating') {
        geo = new THREE.SphereGeometry(0.22, 12, 12);
        mat = new THREE.MeshStandardMaterial({ color: 0x888888, roughness: 0.9 });
        labelText = `${id} (generating...)`;
    } else {
        geo = new THREE.SphereGeometry(0.18, 10, 10);
        mat = new THREE.MeshStandardMaterial({ color: 0x999999, roughness: 1.0 });
        // number first, optional tracker label only when it adds information
        labelText = label && label !== "object" ? `${id} (${label})` : String(id);
    }

    const mesh = new THREE.Mesh(geo, mat);
    mesh.userData.kind = kind;
    mesh.castShadow = true;

    // A visibly spinning ring while generating, so "in progress" reads
    // differently from "unassigned" even though both are grey spheres.
    if (kind === 'generating') {
        const ring = new THREE.Mesh(
            new THREE.TorusGeometry(0.32, 0.02, 8, 24),
            new THREE.MeshBasicMaterial({ color: 0xaaaaaa, wireframe: true })
        );
        ring.rotation.x = Math.PI / 2;
        ring.name = 'spin-ring';
        mesh.add(ring);
    }

    mesh.add(makeLabelSprite(labelText));
    return mesh;
}


function normalizedToWorld(nx, ny) {
    const x = (nx - 0.5) * TABLE_SIZE;
    const z = (ny - 0.5) * TABLE_SIZE;
    return [x, z];
}


function clearRelationshipLines() {
    for (const line of relationshipLines) {
        scene.remove(line);
        line.geometry.dispose();
        line.material.dispose();
    }
    relationshipLines.length = 0;
}


function drawRelationshipLine(x1, z1, x2, z2, proximity) {
    if (proximity === 'far') return;

    const color = proximity === 'near' ? 0x44ff44 : 0x444444;
    const geo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(x1, 0.05, z1),
        new THREE.Vector3(x2, 0.05, z2),
    ]);
    const mat = new THREE.LineBasicMaterial({ color });
    const line = new THREE.Line(geo, mat);
    scene.add(line);
    relationshipLines.push(line);
}


// ── Mock mode ───────────────────────────────────────────
// Lets the normal mapping/rendering path run without live Record3D input.
// Mock objects are posted through /api/mock_scene using the tracker schema.

let mockMode = false;
let mockObjects = [];
let nextMockId = 1;
let draggingKey = null;  // tracker id of the mock object currently being dragged

const raycaster = new THREE.Raycaster();
const pointerNDC = new THREE.Vector2();
let pointerDownPos = null;

function worldToNormalized(x, z) {
    return [x / TABLE_SIZE + 0.5, z / TABLE_SIZE + 0.5];
}

function setPointerNDC(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    pointerNDC.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointerNDC.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
}

async function pushMockObjects() {
    try {
        await fetch('/api/mock_scene', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ objects: mockObjects }),
        });
    } catch (err) {
        console.error('[mock] failed to push objects', err);
    }
}

function findTrackedKey(obj) {
    // Raycasts can hit a loaded mesh child, so walk up to the tracked group.
    let node = obj;
    while (node) {
        const key = Object.keys(meshes).find(k => meshes[k] === node);
        if (key) return key;
        node = node.parent;
    }
    return null;
}

renderer.domElement.addEventListener('pointerdown', (e) => {
    pointerDownPos = { x: e.clientX, y: e.clientY };
    draggingKey = null;
    if (!mockMode) return;

    // A press on a mock object starts repositioning rather than camera orbit.
    setPointerNDC(e);
    raycaster.setFromCamera(pointerNDC, camera);
    const hits = raycaster.intersectObjects(Object.values(meshes), true);
    if (hits.length > 0) {
        const key = findTrackedKey(hits[0].object);
        // Object keys use the numeric tracker id.
        if (key && mockObjects.some(o => String(o.id) === key)) {
            draggingKey = key;
            controls.enabled = false;
        }
    }
});

renderer.domElement.addEventListener('pointermove', (e) => {
    if (!mockMode || !draggingKey) return;

    setPointerNDC(e);
    raycaster.setFromCamera(pointerNDC, camera);
    const tableHits = raycaster.intersectObject(tableMesh, false);
    if (tableHits.length === 0) return;

    const dash = draggingKey.lastIndexOf('-');
    const label = draggingKey.slice(0, dash);
    const id = parseInt(draggingKey.slice(dash + 1), 10);
    const entry = mockObjects.find(o => o.label === label && o.id === id);
    if (!entry) return;

    const point = tableHits[0].point;
    const [nx, ny] = worldToNormalized(point.x, point.z);
    entry.x = Math.min(Math.max(nx, 0), 1);
    entry.y = Math.min(Math.max(ny, 0), 1);
    pushMockObjects();
});

renderer.domElement.addEventListener('pointerup', (e) => {
    controls.enabled = true;

    if (!mockMode || !pointerDownPos) { pointerDownPos = null; draggingKey = null; return; }

    // Distinguish a click from an orbit-drag by movement distance,
    // so OrbitControls keeps working normally in mock mode.
    const moved = Math.hypot(e.clientX - pointerDownPos.x, e.clientY - pointerDownPos.y);
    pointerDownPos = null;

    if (draggingKey) {
        // This gesture repositioned an object, already handled in
        // pointermove. Don't also treat it as a remove/place click.
        draggingKey = null;
        return;
    }

    if (moved > 5) return;

    setPointerNDC(e);
    raycaster.setFromCamera(pointerNDC, camera);

    // Clicking an existing rendered object removes it.
    const objectHits = raycaster.intersectObjects(Object.values(meshes), true);
    if (objectHits.length > 0) {
        const key = findTrackedKey(objectHits[0].object);
        if (key) {
            const dash = key.lastIndexOf('-');
            const label = key.slice(0, dash);
            const id = parseInt(key.slice(dash + 1), 10);
            mockObjects = mockObjects.filter(o => !(o.label === label && o.id === id));
            pushMockObjects();
        }
        return;
    }

    // Otherwise, clicking the table places a new object.
    const tableHits = raycaster.intersectObject(tableMesh, false);
    if (tableHits.length === 0) return;

    const label = window.prompt('What object is this?');
    if (!label || !label.trim()) return;

    const point = tableHits[0].point;
    const [nx, ny] = worldToNormalized(point.x, point.z);

    mockObjects.push({
        id: nextMockId++,
        label: label.trim().toLowerCase(),
        x: Math.min(Math.max(nx, 0), 1),
        y: Math.min(Math.max(ny, 0), 1),
        depth_m: 1.0,   // unused by compute_scene.py, kept for schema parity
    });
    pushMockObjects();
});

const mockToggleBtn = document.getElementById('mock-toggle');
const mockClearBtn = document.getElementById('mock-clear');
const mockHelpEl = document.getElementById('mock-help');

mockToggleBtn.addEventListener('click', () => {
    mockMode = !mockMode;
    mockToggleBtn.textContent = `Mock Mode: ${mockMode ? 'ON' : 'OFF'}`;
    mockHelpEl.textContent = mockMode
        ? 'Click the table to place an object. Click an object to remove it.'
        : '';
});

mockClearBtn.addEventListener('click', () => {
    mockObjects = [];
    pushMockObjects();
});

// Reset scene to a clean participant state. The server clears assignments,
// relations, modifier state and tracked/mock scene data; the browser clears
// its local mirrors immediately.
document.getElementById('scene-reset').addEventListener('click', async () => {
    try {
        await fetch('/api/reset', { method: 'POST' });
    } catch (err) {
        console.error('[reset] failed', err);
        return;
    }

    // clear tracked objects and local state
    assignments = {};
    mockObjects = [];
    for (const key of Object.keys(meshes)) {
        scene.remove(meshes[key]);
        delete meshes[key];
    }

    // Reset the local renderer immediately. /api/reset also clears the
    // saved modifier file, so the next poll remains at these defaults.
    activeModifiers = clampModifiers(DEFAULT_MODIFIERS);
    applyAtmosphere(DEFAULT_MODIFIERS, true);
    applyMistAtTime(performance.now() * 0.001, 0, DEFAULT_MODIFIERS.mist_height, DEFAULT_MODIFIERS.mist_motion);
    rain.visible = false;
    resetLightningClock();
});

// ── Rotation correction ────────────────────────────────
//
// Generated meshes don't come out in a canonical orientation.
// These buttons apply to whatever object key is currently typed in
// the assign-key box, reusing it rather than adding new UI clutter.

async function bumpRotation(axis) {
    const object_key = document.getElementById('assign-key').value.trim();
    if (!object_key) return;
    try {
        await fetch('/api/rotate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ object_key, axis, delta: 90 }),
        });
    } catch (err) {
        console.error('[rotate] failed', err);
    }
}

document.getElementById('rotate-x').addEventListener('click', () => bumpRotation('x'));
document.getElementById('rotate-y').addEventListener('click', () => bumpRotation('y'));
document.getElementById('rotate-z').addEventListener('click', () => bumpRotation('z'));


// ── Conversation input ──────────────────────────────────
// The facilitator selects the study condition and participant in the URL.
// The default stays text so the pre-Phase 6 typed path still works unchanged.
// project design: ?input=voice&participant=P03 keeps study metadata attached
// to each interaction event without adding participant-facing controls.
// academic ref: Hilbert & Redmiles, ACM Computing Surveys 32(4), 2000.
// https://doi.org/10.1145/371578.371593
// ref: https://developer.mozilla.org/en-US/docs/Web/API/URLSearchParams/get
const studyParams = new URLSearchParams(window.location.search);
const inputMode = studyParams.get('input') === 'voice' ? 'voice' : 'text';
const participantId = (studyParams.get('participant') || '').trim() || null;

const converseInput = document.getElementById('converse-input');
const converseButton = document.getElementById('converse-btn');
const converseStatus = document.getElementById('converse-status');
const voiceStatus = document.getElementById('voice-status');

// Keep the study fields beside the command that produced them. The server
// writes them into the existing conversation log after a successful Qwen call.
// academic ref: Hilbert & Redmiles, ACM Computing Surveys 32(4), 2000.
// https://doi.org/10.1145/371578.371593
// ref: https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch
async function sendConverseCommand(voiceCommand = null, voiceLog = null) {
    const command = (voiceCommand ?? converseInput.value).trim();
    if (!command) return false;

    const logFields = voiceLog || {
        raw_transcript: null,
        transcript_attempts: [],
        retry_count: 0,
        confirmation_transcript: null,
        stt_s: null,
    };
    const payload = {
        ...logFields,
        command,
        participant_id: participantId,
        condition: inputMode,
        input_modality: voiceCommand === null ? 'text' : 'voice',
        final_text: command,
    };

    converseStatus.textContent = 'thinking...';
    try {
        const res = await fetch('/api/converse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (data.ok) {
            converseStatus.textContent = `applied: ${command}`;
            if (voiceCommand === null) converseInput.value = '';
            return true;
        }
        converseStatus.textContent = data.error || 'failed, try again';
    } catch (err) {
        console.error('[converse] failed', err);
        converseStatus.textContent = 'conversation service unavailable';
    }
    return false;
}

if (inputMode === 'text') {
    voiceStatus.style.display = 'none';
    converseButton.addEventListener('click', () => sendConverseCommand());
    converseInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') sendConverseCommand();
    });
}


// ── Voice condition ─────────────────────────────────────
// This is the same isolated path qualified on hardware before production:
// DualSense touchpad -> 16 kHz WAV -> Moonshine -> Pocket TTS confirmation
// -> spoken yes/no -> the existing /api/converse endpoint.
//
// AudioWorklet keeps PCM capture in the browser without adding ffmpeg or a
// compressed-media conversion dependency. Moonshine consumes 16 kHz audio.
// academic ref: Choi, "AudioWorklet: The Future of Web Audio", ICMC 2018.
// https://quod.lib.umich.edu/i/icmc/bbp2372.2018.021/1
// academic ref: Jeffries et al., "Moonshine", arXiv:2410.15608.
// https://doi.org/10.48550/arXiv.2410.15608
// ref: https://www.w3.org/TR/webaudio-1.1/#AudioWorklet
// ref: https://www.w3.org/TR/webaudio-1.1/#MediaStreamAudioSourceNode
// ref: https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia
// ref: https://developer.mozilla.org/en-US/docs/Web/API/AudioContext/AudioContext
const voiceSttUrl = 'http://127.0.0.1:8090/transcribe';
const voiceTtsUrl = '/api/tts';
const voiceSampleRate = 16000;

// Chromium exposes the DualSense touchpad CLICK as the extra button after the
// 17-button standard layout. The isolated Opera/macOS hardware test qualified
// buttons[17] as the push-to-talk trigger.
// academic ref: Kun, Paek & Medenica, Interspeech 2007.
// https://doi.org/10.21437/Interspeech.2007-406
// ref: https://developer.mozilla.org/en-US/docs/Web/API/Gamepad_API/Using_the_Gamepad_API
// ref: https://chromium.googlesource.com/chromium/src/+/HEAD/device/gamepad/gamepad_standard_mappings.h
// ref: https://chromium.googlesource.com/chromium/src/+/refs/tags/149.0.7827.155/device/gamepad/game_controller_gamepad.mm
const voiceTalkButton = 17;

let voiceContext = null;
let voiceNode = null;
let voiceRecording = false;
let voiceBusy = false;
let voiceSpeaking = false;
let voiceChunks = [];
let voiceTalkPressed = false;
let pendingVoiceCommand = '';
let awaitingVoiceConfirmation = false;

// Keep rejected command transcripts until one is confirmed. This lets the
// study measure repair friction without creating a separate telemetry system.
// academic ref: Hilbert & Redmiles, ACM Computing Surveys 32(4), 2000.
// https://doi.org/10.1145/371578.371593
// ref: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/push
let voiceTranscriptAttempts = [];
let voiceRetryCount = 0;
let voiceAcceptedStt = null;

// voiceAudio holds the element currently playing so a touchpad press can stop
// it. voiceRawTranscript keeps the untouched Moonshine string for the log after
// the displayed command has had a leading filler removed.
// written from scratch, no external source.
let voiceAudio = null;
let voiceSpeakCancelled = false;
let voiceRawTranscript = '';

async function setupVoice() {
    if (voiceContext) return;

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    voiceContext = new AudioContext({ sampleRate: voiceSampleRate });
    if (voiceContext.sampleRate !== voiceSampleRate) {
        throw new Error(`sample rate is ${voiceContext.sampleRate}, expected ${voiceSampleRate}`);
    }

    await voiceContext.audioWorklet.addModule('./voice_capture_worklet.js');
    const source = voiceContext.createMediaStreamSource(stream);
    voiceNode = new AudioWorkletNode(voiceContext, 'voice-capture', { numberOfOutputs: 0 });
    source.connect(voiceNode);
    voiceNode.port.onmessage = (event) => {
        if (voiceRecording) voiceChunks.push(event.data);
    };
    await voiceContext.resume();
}

function joinVoiceChunks() {
    const length = voiceChunks.reduce((total, chunk) => total + chunk.length, 0);
    const samples = new Float32Array(length);
    let offset = 0;
    for (const chunk of voiceChunks) {
        samples.set(chunk, offset);
        offset += chunk.length;
    }
    return samples;
}

function writeVoiceText(view, offset, text) {
    for (let i = 0; i < text.length; i++) {
        view.setUint8(offset + i, text.charCodeAt(i));
    }
}

function makeVoiceWav(samples) {
    // RIFF/WAVE PCM written directly so Moonshine receives mono signed 16-bit
    // samples at the already-qualified 16 kHz rate.
    // ref: https://learn.microsoft.com/en-us/windows/win32/xaudio2/resource-interchange-file-format--riff-
    // ref: https://learn.microsoft.com/en-us/windows/win32/api/mmreg/ns-mmreg-waveformatex
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);

    writeVoiceText(view, 0, 'RIFF');
    view.setUint32(4, 36 + samples.length * 2, true);
    writeVoiceText(view, 8, 'WAVE');
    writeVoiceText(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, voiceSampleRate, true);
    view.setUint32(28, voiceSampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeVoiceText(view, 36, 'data');
    view.setUint32(40, samples.length * 2, true);

    for (let i = 0; i < samples.length; i++) {
        const sample = Math.max(-1, Math.min(1, samples[i]));
        const pcm = sample < 0 ? sample * 32768 : sample * 32767;
        view.setInt16(44 + i * 2, pcm, true);
    }
    return buffer;
}

async function speakVoiceText(text) {
    // Pocket TTS is the local neural voice already qualified through /api/tts.
    // academic ref: Rouard et al., "Continuous Audio Language Models", 2026.
    // https://doi.org/10.48550/arXiv.2509.06926
    // ref: https://github.com/kyutai-labs/pocket-tts/blob/v2.1.0/pocket_tts/main.py
    // ref: https://developer.mozilla.org/en-US/docs/Web/API/Response/ok
    // ref: https://developer.mozilla.org/en-US/docs/Web/API/Response/blob
    // ref: https://developer.mozilla.org/en-US/docs/Web/API/URL/createObjectURL_static
    // ref: https://developer.mozilla.org/en-US/docs/Web/API/URL/revokeObjectURL_static
    // ref: https://developer.mozilla.org/en-US/docs/Web/API/HTMLAudioElement/Audio
    // ref: https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/play
    //
    // The element is held in voiceAudio so a touchpad press can stop playback.
    // Pausing resolves the same promise as ending, so an interrupted read-back
    // finishes its caller normally instead of hanging.
    // academic ref: Matsuyama et al., Interspeech 2010, barge-in-able dialogue.
    // https://www.isca-archive.org/interspeech_2010/matsuyama10b_interspeech.pdf
    // ref: https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/pause
    // ref: https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/pause_event
    voiceSpeaking = true;
    voiceSpeakCancelled = false;
    let audioUrl = null;
    try {
        const response = await fetch(voiceTtsUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text }),
        });
        if (!response.ok) throw new Error('voice generation failed');

        audioUrl = URL.createObjectURL(await response.blob());
        // A press can land while the audio is still being fetched, before there
        // is an element to pause. Playback is skipped in that case so the
        // read-back never starts on top of a recording already in progress.
        // written from scratch, no external source.
        if (voiceSpeakCancelled) return;

        const audio = new Audio(audioUrl);
        voiceAudio = audio;
        await new Promise((resolve, reject) => {
            audio.onended = resolve;
            audio.onpause = resolve;
            audio.onerror = () => reject(new Error('voice playback failed'));
            audio.play().catch(reject);
        });
    } finally {
        voiceAudio = null;
        voiceSpeaking = false;
        if (audioUrl) URL.revokeObjectURL(audioUrl);
    }
}

// Moonshine returns capitalised, punctuated text, so the raw string is reduced
// to bare lowercase words before any answer is matched.
// academic ref: Jeffries et al., "Moonshine", arXiv:2410.15608.
// https://doi.org/10.48550/arXiv.2410.15608
// ref: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/replace
function normalizeVoiceAnswer(text) {
    return (text || '').toLowerCase().replace(/[^a-z\s]/g, ' ').replace(/\s+/g, ' ').trim();
}

function voiceAnswerWords(text) {
    const value = normalizeVoiceAnswer(text);
    return value ? value.split(' ') : [];
}

// Matching runs on whole words, not on the whole string and not on substrings.
// Whole-string matching rejected "Yeah yes" when Moonshine prepended a word the
// participant did not say. Substring matching would find "no" inside "nope",
// "not" and "know". Requiring exactly one polarity means a transcript holding
// both a yes word and a no word is treated as unclear and asked again, which is
// the safe direction: a wrongly accepted confirmation generates the wrong scene,
// a wrongly rejected one costs one repeat.
// academic ref: Clark & Schaefer, Cognitive Science 13(2), 1989.
// https://doi.org/10.1207/s15516709cog1302_7
// project tuning: the word lists themselves are chosen for this study, not taken
// from a published vocabulary.
const VOICE_YES_WORDS = ['yes', 'yeah', 'yep', 'correct', 'right'];
const VOICE_NO_WORDS = ['no', 'nope', 'nah', 'incorrect', 'wrong'];

// A yes or no answer is at most two words. Anything longer is the participant
// giving a new command instead of answering, which is treated as such rather
// than scanned for a yes word. Without this, a command carrying a leading junk
// word ("Yeah, make it sunset") matched as a yes and confirmed the previous
// command. The cost is that a long-winded confirmation such as "yep that is it"
// is read back as a command, which the participant can reject.
// academic ref: Clark & Schaefer, Cognitive Science 13(2), 1989.
// https://doi.org/10.1207/s15516709cog1302_7
// project tuning: the two-word ceiling is set for this study.
const VOICE_ANSWER_MAX_WORDS = 2;

function voiceAnswerIsYes(text) {
    const words = voiceAnswerWords(text);
    if (!words.length || words.length > VOICE_ANSWER_MAX_WORDS) return false;
    const hasYes = words.some(word => VOICE_YES_WORDS.includes(word));
    const hasNo = words.some(word => VOICE_NO_WORDS.includes(word));
    return hasYes && !hasNo;
}

function voiceAnswerIsNo(text) {
    const words = voiceAnswerWords(text);
    if (!words.length || words.length > VOICE_ANSWER_MAX_WORDS) return false;
    const hasYes = words.some(word => VOICE_YES_WORDS.includes(word));
    const hasNo = words.some(word => VOICE_NO_WORDS.includes(word));
    return hasNo && !hasYes;
}

// Moonshine attaches a word the participant did not say to the front of some
// transcripts. Silence trimming was tested across 50 clips at four thresholds
// and made this worse, and a 256 ms pre-roll gave no benefit, so the transcript
// is repaired after the fact instead. Only one leading filler is removed, and
// only when words remain after it, so a real command is never emptied. The
// untouched string is still written to the log as raw_transcript.
// academic ref: Jeffries et al., "Moonshine", arXiv:2410.15608.
// https://doi.org/10.48550/arXiv.2410.15608
// ref: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/RegExp/RegExp
// project tuning: the filler list is drawn from this project's own corpus runs.
// Spatial words such as "right" and lighting words such as "well" are excluded
// because they can legitimately open a command.
const VOICE_LEADING_FILLERS = [
    'thank you', 'thanks', 'yeah', 'yep', 'yes', 'okay', 'ok',
    'umm', 'um', 'uh', 'hmm', 'oh', 'so', 'and', 'hey', 'hi',
];

function stripLeadingFiller(text) {
    const trimmed = (text || '').trim();
    for (const filler of VOICE_LEADING_FILLERS) {
        const pattern = new RegExp('^' + filler + '[\\s,.!?]+', 'i');
        if (!pattern.test(trimmed)) continue;
        const rest = trimmed.replace(pattern, '').trim();
        if (rest) return rest.charAt(0).toUpperCase() + rest.slice(1);
    }
    return trimmed;
}

// Voice assignment uses one narrow grammar: "object <id> is <meaning>".
// Digits and one-to-ten word forms are accepted because speech transcription
// may represent a spoken number either way. The meaning stays unrestricted.
// ref: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/RegExp
// ref: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/match
// project decision: 28 aug 2026. Keep assignment routing deterministic rather
// than sending an object-assignment command through the atmosphere LLM.
const VOICE_OBJECT_NUMBER_WORDS = {
    one: '1', two: '2', three: '3', four: '4', five: '5',
    six: '6', seven: '7', eight: '8', nine: '9', ten: '10',
};

function parseVoiceAssignment(text) {
    const match = (text || '').trim().match(
        /^object\s+(?:number\s+)?(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+is\s+(.+?)\s*[.!?]*$/i
    );
    if (!match) return null;

    const spokenKey = match[1].toLowerCase();
    const objectKey = /^\d+$/.test(spokenKey)
        ? String(parseInt(spokenKey, 10))
        : VOICE_OBJECT_NUMBER_WORDS[spokenKey];
    const meaning = match[2].replace(/[.!?]+$/, '').trim();
    if (!objectKey || !meaning) return null;
    return { object_key: objectKey, meaning };
}

async function sendVoiceAssignment(assignment) {
    converseStatus.textContent = `assigning object ${assignment.object_key}...`;
    try {
        // Reuse the existing assignment endpoint; no server or generation path
        // changes are needed for voice assignment.
        // ref: https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch
        // ref: https://developer.mozilla.org/en-US/docs/Web/API/Response/ok
        const response = await fetch('/api/assign', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(assignment),
        });
        if (!response.ok) {
            converseStatus.textContent = 'assignment failed, try again';
            return false;
        }

        // Mirror the accepted spoken assignment in the existing assignment UI
        // so the facilitator can see exactly which id and meaning were routed.
        document.getElementById('assign-key').value = assignment.object_key;
        document.getElementById('assign-meaning').value = assignment.meaning;
        converseStatus.textContent = `assigned object ${assignment.object_key}: ${assignment.meaning}`;
        return true;
    } catch (err) {
        console.error('[voice assign] failed', err);
        converseStatus.textContent = 'assignment service unavailable';
        return false;
    }
}

async function routeAcceptedVoiceCommand(command, voiceLog) {
    const assignment = parseVoiceAssignment(command);
    if (assignment) return sendVoiceAssignment(assignment);
    return sendConverseCommand(command, voiceLog);
}

function startVoiceRecording() {
    // A press during the read-back stops it rather than being discarded, and
    // abandons the command that was being confirmed, so whatever is said next
    // arrives as a new command. Push-to-talk means the interruption is an
    // explicit button press, not speech detected over the system's own audio,
    // so the false-barge-in problem of open-microphone systems does not apply.
    // academic ref: Matsuyama et al., Interspeech 2010, barge-in-able dialogue.
    // https://www.isca-archive.org/interspeech_2010/matsuyama10b_interspeech.pdf
    // academic ref: Lin et al., "Duplex Conversation", arXiv:2205.15060.
    // https://doi.org/10.48550/arXiv.2205.15060
    // ref: https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/pause
    if (voiceSpeaking) {
        voiceSpeakCancelled = true;
        if (voiceAudio) voiceAudio.pause();
        voiceSpeaking = false;
        if (awaitingVoiceConfirmation) {
            awaitingVoiceConfirmation = false;
            pendingVoiceCommand = '';
            voiceRetryCount += 1;
        }
    }

    // A press that lands while transcription or the Qwen call is in flight is
    // still refused, because a second command cannot start mid-generation. It
    // now says so on screen instead of doing nothing visible.
    // written from scratch, no external source.
    if (!voiceContext || voiceRecording || voiceBusy) {
        const blocked = [];
        if (!voiceContext) blocked.push('press Enable Voice first');
        if (voiceRecording) blocked.push('already recording');
        if (voiceBusy) blocked.push('still working, wait');
        console.log('[voice] press ignored |', blocked.join(', '));
        converseStatus.textContent = `press ignored | ${blocked.join(', ')}`;
        return;
    }

    voiceChunks = [];
    voiceRecording = true;
    converseStatus.textContent = awaitingVoiceConfirmation
        ? 'listening for yes or no...'
        : 'listening...';
}

async function transcribeVoiceRecording() {
    const wav = makeVoiceWav(joinVoiceChunks());
    // Raw WAV body matches the qualified Moonshine server contract.
    // ref: https://developer.mozilla.org/en-US/docs/Web/API/Window/fetch
    // ref: https://developer.mozilla.org/en-US/docs/Web/API/Response/ok
    const response = await fetch(voiceSttUrl, { method: 'POST', body: wav });
    const result = await response.json();
    if (!response.ok || !result.ok) {
        throw new Error(result.error || 'transcription failed');
    }
    return result;
}

// Every status write that follows an await is guarded, because a touchpad press
// during the read-back starts a new recording and that recording owns the status
// line from then on. Without the guard the interrupted command overwrote
// "listening..." a few milliseconds later and the participant saw no sign that
// the button had worked.
// written from scratch, no external source.
function setVoiceStatus(text) {
    if (!voiceRecording) converseStatus.textContent = text;
}

// Spoken read-back is a project reliability decision after the live STT
// mis-hearing test. The acknowledgement follows conversational grounding.
// academic ref: Clark & Schaefer, Cognitive Science 13(2), 1989.
// https://doi.org/10.1207/s15516709cog1302_7
async function handleVoiceCommand(result) {
    const rawText = result.text || '';
    const command = stripLeadingFiller(rawText);
    converseInput.value = command;

    if (!command) {
        converseStatus.textContent = `nothing heard, press and speak again | ${result.stt_s}s`;
        return;
    }

    pendingVoiceCommand = command;
    voiceRawTranscript = rawText;
    voiceTranscriptAttempts.push(rawText);
    voiceAcceptedStt = result.stt_s;
    awaitingVoiceConfirmation = true;
    converseStatus.textContent = `heard | ${result.stt_s}s`;
    await speakVoiceText(`Did you say: ${command}?`);
    setVoiceStatus('say yes or no');
}

async function handleVoiceConfirmation(result) {
    const answer = result.text || '';

    // Too many words to be an answer, so it is a new command. The abandoned
    // command stays in voiceTranscriptAttempts and the retry count rises, so the
    // study still sees the repair.
    if (voiceAnswerWords(answer).length > VOICE_ANSWER_MAX_WORDS) {
        awaitingVoiceConfirmation = false;
        pendingVoiceCommand = '';
        voiceRetryCount += 1;
        await handleVoiceCommand(result);
        return;
    }

    if (voiceAnswerIsYes(answer)) {
        // Busy is raised only around the Qwen call, so a press during the
        // read-back can interrupt but a press mid-generation cannot.
        // written from scratch, no external source.
        let applied = false;
        voiceBusy = true;
        try {
            applied = await routeAcceptedVoiceCommand(pendingVoiceCommand, {
                raw_transcript: voiceRawTranscript,
                transcript_attempts: [...voiceTranscriptAttempts],
                retry_count: voiceRetryCount,
                confirmation_transcript: answer,
                stt_s: voiceAcceptedStt,
            });
        } finally {
            voiceBusy = false;
        }
        if (!applied) return;
        awaitingVoiceConfirmation = false;
        pendingVoiceCommand = '';
        voiceRawTranscript = '';
        voiceTranscriptAttempts = [];
        voiceRetryCount = 0;
        voiceAcceptedStt = null;
        await speakVoiceText('Got it.');
        return;
    }

    if (voiceAnswerIsNo(answer)) {
        voiceRetryCount += 1;
        awaitingVoiceConfirmation = false;
        pendingVoiceCommand = '';
        converseInput.value = '';
        converseStatus.textContent = 'ready to try again';
        await speakVoiceText('Okay, try again.');
        setVoiceStatus('ready to try again');
        return;
    }

    // Neither polarity, or nothing heard. The transcript is shown so a failure
    // is diagnosable during the study instead of after it.
    // academic ref: Hilbert & Redmiles, ACM Computing Surveys 32(4), 2000.
    // https://doi.org/10.1145/371578.371593
    const heard = answer || '(nothing heard)';
    console.log('[voice] confirmation unclear | raw:', heard,
                '| normalized:', normalizeVoiceAnswer(answer) || '(empty)');
    converseStatus.textContent = `please say yes or no | heard: ${heard}`;
    await speakVoiceText('Please say yes or no.');
    setVoiceStatus(`please say yes or no | heard: ${heard}`);
}

async function stopVoiceRecording() {
    if (!voiceRecording) return;
    voiceRecording = false;

    // Busy covers the transcription request only. It is cleared before the
    // read-back so the read-back stays interruptible. An earlier version left
    // busy raised across the read-back and restored it afterwards, which could
    // land while a barge-in recording was already running and strand
    // voiceRecording on true until the page was refreshed.
    // written from scratch, no external source.
    let result = null;
    voiceBusy = true;
    converseStatus.textContent = 'transcribing...';
    try {
        result = await transcribeVoiceRecording();
    } catch (err) {
        console.error('[voice] transcription failed', err);
        converseStatus.textContent = `voice error: ${err.message}`;
        return;
    } finally {
        voiceBusy = false;
    }

    try {
        if (awaitingVoiceConfirmation) await handleVoiceConfirmation(result);
        else await handleVoiceCommand(result);
    } catch (err) {
        console.error('[voice] failed', err);
        converseStatus.textContent = `voice error: ${err.message}`;
    }
}

// Read the latest Gamepad object each frame rather than holding a stale object.
// ref: https://www.w3.org/TR/gamepad/#dom-navigator-getgamepads
// ref: https://developer.mozilla.org/en-US/docs/Web/API/Gamepad_API/Using_the_Gamepad_API
function pollVoiceGamepad() {
    let gamepad = null;
    for (const pad of navigator.getGamepads()) {
        if (pad) {
            gamepad = pad;
            break;
        }
    }

    if (!gamepad) {
        voiceStatus.textContent = 'controller: connect DualSense and press touchpad once';
        voiceTalkPressed = false;
    } else if (gamepad.mapping !== 'standard') {
        voiceStatus.textContent = `controller: ${gamepad.id} | not armed`;
        voiceTalkPressed = false;
    } else if (gamepad.buttons.length <= voiceTalkButton) {
        voiceStatus.textContent = `controller: ${gamepad.id} | touchpad unavailable`;
        voiceTalkPressed = false;
    } else {
        voiceStatus.textContent = `controller: ${gamepad.id} | touchpad ready`;
        const pressed = gamepad.buttons[voiceTalkButton].pressed;
        if (voiceContext && pressed && !voiceTalkPressed) startVoiceRecording();
        if (voiceContext && !pressed && voiceTalkPressed) stopVoiceRecording();
        voiceTalkPressed = pressed;
    }

    requestAnimationFrame(pollVoiceGamepad);
}

if (inputMode === 'voice') {
    converseInput.readOnly = true;
    converseInput.placeholder = 'latest voice transcript';
    converseButton.textContent = 'Enable Voice';
    converseStatus.textContent = 'voice mode: enable microphone';
    voiceStatus.textContent = 'controller: connect DualSense and press touchpad once';

    converseButton.addEventListener('click', async () => {
        try {
            await setupVoice();
            converseButton.textContent = 'Voice Ready';
            converseButton.disabled = true;
            converseStatus.textContent = 'voice ready';
        } catch (err) {
            console.error('[voice] setup failed', err);
            converseStatus.textContent = `voice error: ${err.message}`;
        }
    });

    requestAnimationFrame(pollVoiceGamepad);
}


// ── Scene polling (object positions) ───────────────────

async function fetchScene() {
    try {
        const res = await fetch('/api/scene');
        if (!res.ok) return null;
        return await res.json();
    } catch {
        return null;
    }
}


let assignments = {};

async function fetchAssignments() {
    try {
        const res = await fetch('/api/assignments');
        if (!res.ok) return null;
        return await res.json();
    } catch {
        return null;
    }
}


// ── Interstitial relations ─────────────────────────────
// Relation records are keyed by meaning-pair server-side. Local mesh and
// proximity state use tracker-id pairs so physical identity stays stable.
let relations = {};
let lastProximity = {};
let interstitialMeshes = {};

async function fetchRelations() {
    try {
        const res = await fetch('/api/relations');
        if (!res.ok) return null;
        return await res.json();
    } catch {
        return null;
    }
}

function slugify(text) {
    return text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'asset';
}

function pairSlug(meaningA, meaningB) {
    // must match serve.py's _pair_slug exactly: order-independent
    return [slugify(meaningA), slugify(meaningB)].sort().join('__');
}

function createInterstitialPlaceholder() {
    // placeholder shown immediately, swapped by createInterstitialMesh
    // below once a real mesh_url loads, same pattern as
    // createAssignmentMesh's box placeholder for regular objects.
    const geo = new THREE.OctahedronGeometry(0.15);
    const mat = new THREE.MeshStandardMaterial({
        color: 0x66ccff, emissive: 0x224466, transparent: true, opacity: 0.85,
    });
    return new THREE.Mesh(geo, mat);
}

function createInterstitialMesh(relRecord) {
    // Reuse the normal generated-mesh loader for connector objects.
    const group = new THREE.Group();
    const placeholder = createInterstitialPlaceholder();
    group.add(placeholder);
    if (relRecord.mesh_url) {
        // Connector meshes use a fixed smaller scale; gap-distance scaling is not wired in.
        loadGeneratedMesh(group, relRecord.mesh_url, placeholder, null, 0.35);
    }
    return group;
}


function updateScene(data) {
    if (!data || !data.objects) return;

    const objects = data.objects;
    const relationships = data.relationships || [];
    const activeKeys = new Set();

    for (const obj of objects) {
        // Tracker id owns physical identity; labels are not used as keys.
        const key = String(obj.id);
        activeKeys.add(key);

        const [wx, wz] = normalizedToWorld(obj.x, obj.y);
        const assignment = assignments[key] || null;
        const desiredKind = !assignment
            ? 'unassigned'
            : assignment.status === 'ready' ? 'ready'
            : assignment.status === 'failed' ? 'failed'
            : 'generating';

        const existing = meshes[key];

        if (existing && existing.userData.kind === desiredKind) {
            // Same kind as last poll: move it without regenerating its meaning.
            existing.position.x += (wx - existing.position.x) * 0.3;
            existing.position.z += (wz - existing.position.z) * 0.3;

            if (desiredKind === 'ready' && assignment && assignment.rotation) {
                syncRotation(existing, assignment.rotation);
            }
        } else {
            // First sighting, or assignment status just changed
            // (unassigned -> generating -> ready): swap appearance.
            if (existing) scene.remove(existing);
            const mesh = createAssignmentMesh(obj.id, obj.label, assignment);
            mesh.position.set(wx, OBJECT_HEIGHT / 2, wz);
            scene.add(mesh);
            meshes[key] = mesh;
        }
    }

    // Remove objects no longer detected
    for (const key of Object.keys(meshes)) {
        if (!activeKeys.has(key)) {
            scene.remove(meshes[key]);
            delete meshes[key];
        }
    }

    // Relationship lines + interstitial trigger.
    clearRelationshipLines();
    const activePairKeys = new Set();
    for (const rel of relationships) {
        const fromObj = objects.find(
            o => o.label === rel.from && o.id === rel.from_id
        );
        const toObj = objects.find(
            o => o.label === rel.to && o.id === rel.to_id
        );
        if (!fromObj || !toObj) continue;

        const [x1, z1] = normalizedToWorld(fromObj.x, fromObj.y);
        const [x2, z2] = normalizedToWorld(toObj.x, toObj.y);
        drawRelationshipLine(x1, z1, x2, z2, rel.proximity);

        const idA = Math.min(rel.from_id, rel.to_id);
        const idB = Math.max(rel.from_id, rel.to_id);
        const pairKey = `${idA}-${idB}`;
        const wasProximity = lastProximity[pairKey];
        lastProximity[pairKey] = rel.proximity;

        if (rel.proximity !== 'near') {
            // left "near": drop any interstitial mesh, this is the
            // reversibility rule, distance alone decides
            if (interstitialMeshes[pairKey]) {
                scene.remove(interstitialMeshes[pairKey]);
                delete interstitialMeshes[pairKey];
            }
            continue;
        }

        activePairKeys.add(pairKey);
        // Object keys use the numeric tracker id.
        const keyA = String(fromObj.id);
        const keyB = String(toObj.id);
        const assignA = assignments[keyA];
        const assignB = assignments[keyB];
        const bothReady = assignA && assignB &&
            assignA.status === 'ready' && assignB.status === 'ready';

        if (bothReady && wasProximity !== 'near') {
            // just crossed INTO near with two settled meanings: fire
            // the trigger. harmless if it fires again, the server
            // no-ops on an existing pair_slug.
            fetch('/api/relate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ object_key_a: keyA, object_key_b: keyB }),
            }).catch(err => console.error('[relate] failed', err));
        }

        if (bothReady) {
            const pSlug = pairSlug(
                assignA.generation_meaning || assignA.meaning,
                assignB.generation_meaning || assignB.meaning
            );
            const relRecord = relations[pSlug];
            if (relRecord && relRecord.status === 'ready') {
                if (!interstitialMeshes[pairKey]) {
                    interstitialMeshes[pairKey] = createInterstitialMesh(relRecord);
                    scene.add(interstitialMeshes[pairKey]);
                }
                interstitialMeshes[pairKey].position.set(
                    (x1 + x2) / 2, OBJECT_HEIGHT / 4, (z1 + z2) / 2
                );
            }
            // Generating or not yet triggered: nothing is shown until ready.
        }
    }

    // clean up interstitial meshes for pairs that dropped off the
    // relationships list entirely (an object left the table)
    for (const pairKey of Object.keys(interstitialMeshes)) {
        if (!activePairKeys.has(pairKey)) {
            scene.remove(interstitialMeshes[pairKey]);
            delete interstitialMeshes[pairKey];
        }
    }

    document.getElementById('count').textContent = objects.length;
    document.getElementById('status').textContent = 'live';
    document.getElementById('known-objects').textContent =
        activeKeys.size > 0 ? `Known: ${Array.from(activeKeys).join(', ')}` : '';
}


// ── Assignment UI ──────────────────────────────────────

document.getElementById('assign-btn').addEventListener('click', async () => {
    const keyEl = document.getElementById('assign-key');
    const meaningEl = document.getElementById('assign-meaning');
    const object_key = keyEl.value.trim();
    const meaning = meaningEl.value.trim();
    if (!object_key || !meaning) return;

    try {
        await fetch('/api/assign', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ object_key, meaning }),
        });
    } catch (err) {
        console.error('[assign] failed', err);
    }
});


// ── Modifier polling ────────────────────────────────────
// The server returns the final 12-field semantic atmosphere state.
// applyAtmosphere maps those fields deterministically to Three.js controls.

async function fetchModifiers() {
    try {
        const res = await fetch('/api/modifiers');
        if (!res.ok) return null;
        return await res.json();
    } catch {
        return null;
    }
}


function applyModifiers(mods) {
    if (!mods) return;
    applyAtmosphere(mods);
}


// ── Polling loops ──────────────────────────────────────

setInterval(async () => {
    const data = await fetchScene();
    if (data) {
        updateScene(data);
    } else {
        document.getElementById('status').textContent = 'no data';
    }
}, SCENE_POLL_MS);

setInterval(async () => {
    const mods = await fetchModifiers();
    if (mods) applyModifiers(mods);
}, MODIFIER_POLL_MS);

setInterval(async () => {
    const data = await fetchAssignments();
    if (data) assignments = data;
}, 500);

setInterval(async () => {
    const data = await fetchRelations();
    if (data) relations = data;
}, 500);

setInterval(pollCalibration, CALIBRATION_POLL_MS);


// ── Render loop ────────────────────────────────────────

function animate(now) {
    requestAnimationFrame(animate);
    controls.update();
    calibUpdate(now);
    updateAtmosphere(now * 0.001);
    for (const mesh of Object.values(meshes)) {
        const ring = mesh.getObjectByName('spin-ring');
        if (ring) ring.rotation.z += 0.05;
    }
    renderer.render(scene, camera);
}
requestAnimationFrame(animate);


// Handle window resize
window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});

