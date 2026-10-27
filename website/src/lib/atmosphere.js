// Port of the Phase 5E deterministic atmosphere mapping from
// phase3-tabletop/rendering/index.html (lines ~605–1030, Three.js r170).
// Constants, layer configs and mapping curves are copied unchanged; only the
// structure is wrapped in a class so the website can own several scenes.
import * as THREE from 'three';
import { Sky } from 'three/examples/jsm/objects/Sky.js';
import { ImprovedNoise } from 'three/examples/jsm/math/ImprovedNoise.js';

export const TABLE_SIZE = 10;
export const DEFAULT_MODIFIERS = {
  sky_elevation: 45, light_elevation: 45, light_azimuth: 45, light_level: 0.65,
  light_warmth: 0, sky_haze: 0.2, mist_amount: 0, mist_height: 0.35, mist_motion: 0.25,
  rain_amount: 0, lightning_amount: 0, mood: 'neutral',
};

const clamp = THREE.MathUtils.clamp;
const lerp = THREE.MathUtils.lerp;
function smoothstep(e0, e1, v) { const x = clamp((v - e0) / (e1 - e0), 0, 1); return x * x * (3 - 2 * x); }

export function clampModifiers(raw) {
  return {
    sky_elevation: clamp(Number(raw.sky_elevation ?? 45), -12, 90),
    light_elevation: clamp(Number(raw.light_elevation ?? 45), 0, 90),
    light_azimuth: ((Number(raw.light_azimuth ?? 45) % 360) + 360) % 360,
    light_level: clamp(Number(raw.light_level ?? 0.65), 0, 1),
    light_warmth: clamp(Number(raw.light_warmth ?? 0), -1, 1),
    sky_haze: clamp(Number(raw.sky_haze ?? 0.2), 0, 1),
    mist_amount: clamp(Number(raw.mist_amount ?? 0), 0, 1),
    mist_height: clamp(Number(raw.mist_height ?? 0.35), 0, 1),
    mist_motion: clamp(Number(raw.mist_motion ?? 0.25), 0, 1),
    rain_amount: clamp(Number(raw.rain_amount ?? 0), 0, 1),
    lightning_amount: clamp(Number(raw.lightning_amount ?? 0), 0, 1),
    mood: String(raw.mood ?? 'neutral'),
  };
}

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
      const px = u * 3.3, py = v * 3.3;
      const coarse = (noise.noise(px, seed, py) + 1) * 0.5;
      const mid = (noise.noise(px * 1.9 + 13.2, seed + 7.1, py * 1.9 + 5.8) + 1) * 0.5;
      const fine = (noise.noise(px * 3.7 + 23.4, seed + 13.7, py * 3.7 + 17.2) + 1) * 0.5;
      const n = 0.64 * coarse + 0.26 * mid + 0.10 * fine;
      let alpha = smoothstep(0.33, 0.70, n);
      alpha *= smoothstep(0, 0.06, u) * smoothstep(0, 0.06, 1 - u) * smoothstep(0, 0.06, v) * smoothstep(0, 0.06, 1 - v);
      const i = (y * size + x) * 4;
      const value = Math.round(alpha * 255);
      image.data[i] = image.data[i + 1] = image.data[i + 2] = value;
      image.data[i + 3] = 255;
    }
  }
  ctx.putImageData(image, 0, 0);
  const t = new THREE.CanvasTexture(canvas);
  t.minFilter = t.magFilter = THREE.LinearFilter;
  return t;
}

const MIST_CONFIGS = [
  { y: 0.12, wobble: 0.02, size: 20, opacityA: 0.072, opacityB: 0.055, sourceA: 0, sourceB: 1, speedAX: 0.018, speedAZ: 0.007, speedBX: -0.009, speedBZ: 0.014, rotA: 0.0035, rotB: -0.0025, phase: 0.0 },
  { y: 0.25, wobble: 0.024, size: 19, opacityA: 0.065, opacityB: 0.050, sourceA: 1, sourceB: 2, speedAX: -0.015, speedAZ: 0.011, speedBX: 0.011, speedBZ: -0.009, rotA: -0.0025, rotB: 0.0035, phase: 0.8 },
  { y: 0.42, wobble: 0.03, size: 18, opacityA: 0.058, opacityB: 0.045, sourceA: 2, sourceB: 0, speedAX: 0.013, speedAZ: -0.011, speedBX: -0.007, speedBZ: 0.012, rotA: 0.0025, rotB: -0.002, phase: 1.7 },
  { y: 0.64, wobble: 0.035, size: 17, opacityA: 0.052, opacityB: 0.040, sourceA: 0, sourceB: 2, speedAX: -0.011, speedAZ: -0.008, speedBX: 0.008, speedBZ: 0.010, rotA: -0.002, rotB: 0.003, phase: 2.5 },
  { y: 0.90, wobble: 0.04, size: 16, opacityA: 0.045, opacityB: 0.034, sourceA: 1, sourceB: 0, speedAX: 0.009, speedAZ: 0.009, speedBX: -0.006, speedBZ: -0.007, rotA: 0.0018, rotB: -0.0026, phase: 3.2 },
  { y: 1.18, wobble: 0.045, size: 15, opacityA: 0.038, opacityB: 0.029, sourceA: 2, sourceB: 1, speedAX: -0.007, speedAZ: 0.006, speedBX: 0.005, speedBZ: -0.005, rotA: -0.0018, rotB: 0.0022, phase: 3.9 },
];
const RAIN_COUNT = 450;

const wrapOffset = (v) => ((v % 1) + 1) % 1;

export class Atmosphere {
  constructor(renderer, scene) {
    this.renderer = renderer;
    this.scene = scene;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;

    // key light
    const dir = new THREE.DirectionalLight(0xffffff, 1.0);
    dir.castShadow = true;
    Object.assign(dir.shadow.camera, { left: -TABLE_SIZE, right: TABLE_SIZE, top: TABLE_SIZE, bottom: -TABLE_SIZE, near: 0.5, far: 50 });
    dir.shadow.mapSize.set(2048, 2048);
    dir.shadow.bias = -0.001;
    scene.add(dir);
    this.dirLight = dir;

    // procedural sky + PMREM environment
    this.sky = new Sky();
    this.sky.scale.setScalar(450000);
    this.skyUniforms = this.sky.material.uniforms;
    this.skySun = new THREE.Vector3();
    this.envScene = new THREE.Scene();
    this.envScene.add(this.sky);
    this.pmrem = new THREE.PMREMGenerator(renderer);
    this.envTarget = null;

    // mist
    const sources = [makeMistTexture(0), makeMistTexture(17), makeMistTexture(41)];
    this.mistGroups = MIST_CONFIGS.map((config) => {
      const group = new THREE.Group();
      const mk = (src, opacity, size, tint) => {
        const alphaMap = sources[src].clone();
        alphaMap.wrapS = alphaMap.wrapT = THREE.RepeatWrapping;
        alphaMap.needsUpdate = true;
        const m = new THREE.Mesh(new THREE.PlaneGeometry(size, size), new THREE.MeshStandardMaterial({
          color: tint, roughness: 1, metalness: 0, transparent: true, opacity, alphaMap, depthWrite: false, side: THREE.DoubleSide,
        }));
        m.rotation.x = -Math.PI / 2;
        return m;
      };
      const layerA = mk(config.sourceA, config.opacityA, config.size, 0xb9c6d6);
      const layerB = mk(config.sourceB, config.opacityB, config.size * 0.96, 0xc7d2df);
      layerB.position.y = 0.01;
      layerB.rotation.z = Math.PI * 0.18;
      group.userData = { config, layerA, layerB };
      group.add(layerA, layerB);
      scene.add(group);
      return group;
    });

    // rain
    this.rainBase = Array.from({ length: RAIN_COUNT }, (_, i) => ({
      x: ((((i * 73) % 1000) / 1000) - 0.5) * TABLE_SIZE * 1.35,
      z: ((((i * 37 + 211) % 1000) / 1000) - 0.5) * TABLE_SIZE * 1.35,
      y0: 0.4 + ((((i * 91 + 17) % 1000) / 1000) * 8.5),
      speed: 5.2 + ((((i * 53 + 101) % 1000) / 1000) * 2.8),
      length: 0.16 + ((((i * 29 + 401) % 1000) / 1000) * 0.20),
    }));
    this.rainPositions = new Float32Array(RAIN_COUNT * 6);
    const geo = new THREE.BufferGeometry();
    this.rainAttr = new THREE.BufferAttribute(this.rainPositions, 3);
    this.rainAttr.setUsage(THREE.DynamicDrawUsage);
    geo.setAttribute('position', this.rainAttr);
    this.rainMaterial = new THREE.LineBasicMaterial({ color: 0xa9bed0, transparent: true, opacity: 0, depthWrite: false });
    this.rain = new THREE.LineSegments(geo, this.rainMaterial);
    this.rain.renderOrder = 30;
    this.rain.frustumCulled = false;
    scene.add(this.rain);

    this.active = clampModifiers(DEFAULT_MODIFIERS);
    this.baseLight = 1;
    this.baseExposure = 0.6;
    this.nextFlashAt = 3.5;
    this.flashStartedAt = null;
    this.apply(DEFAULT_MODIFIERS, true);
  }

  setLightAngle(el, az) {
    const dist = TABLE_SIZE * 3;
    const e = THREE.MathUtils.degToRad(el), a = THREE.MathUtils.degToRad(az);
    this.dirLight.position.set(dist * Math.cos(e) * Math.cos(a), dist * Math.sin(e), dist * Math.cos(e) * Math.sin(a));
  }

  setSkySun(el, az = 180) {
    this.skySun.setFromSphericalCoords(1, THREE.MathUtils.degToRad(90 - el), THREE.MathUtils.degToRad(az));
    this.skyUniforms.sunPosition.value.copy(this.skySun);
  }

  refreshEnvironment() {
    if (this.sky.parent !== this.envScene) this.envScene.add(this.sky);
    const next = this.pmrem.fromScene(this.envScene);
    if (this.envTarget) this.envTarget.dispose();
    this.envTarget = next;
    this.scene.environment = next.texture;
    if (this.sky.parent !== this.scene) this.scene.add(this.sky);
  }

  apply(mods, force = false, skipEnv = false) {
    const next = clampModifiers({ ...this.active, ...mods });
    const prev = this.active;
    this.active = next;
    this.setSkySun(next.sky_elevation, 180);
    this.setLightAngle(next.light_elevation, next.light_azimuth);
    this.baseLight = lerp(0.45, 6.0, Math.pow(next.light_level, 1.15));
    const w = (next.light_warmth + 1) * 0.5;
    const key = w < 0.5
      ? new THREE.Color(0xbcd1f0).lerp(new THREE.Color(0xffffff), w / 0.5)
      : new THREE.Color(0xffffff).lerp(new THREE.Color(0xff9f5f), (w - 0.5) / 0.5);
    this.dirLight.color.copy(key);
    this.dirLight.intensity = this.baseLight;
    const u = this.skyUniforms;
    u.turbidity.value = lerp(2.0, 12.0, next.sky_haze);
    u.rayleigh.value = lerp(1.8, 0.45, next.sky_haze);
    u.mieCoefficient.value = lerp(0.002, 0.010, next.sky_haze);
    u.mieDirectionalG.value = lerp(0.80, 0.90, next.sky_haze);
    if (force || (!skipEnv && (next.sky_elevation !== prev.sky_elevation || next.sky_haze !== prev.sky_haze))) this.refreshEnvironment();
    this.scene.environmentIntensity = lerp(2.4, 0.25, next.light_level);
    this.baseExposure = lerp(0.78, 0.48, next.light_level);
    this.renderer.toneMappingExposure = this.baseExposure;
    if (prev.lightning_amount <= 0.01 && next.lightning_amount > 0.01) this.resetLightning();
    if (next.lightning_amount <= 0.01) this.flashStartedAt = null;
    return next;
  }

  resetLightning(now = performance.now() * 0.001) { this.nextFlashAt = now + 3.5; this.flashStartedAt = null; }

  lightningStrength(t) {
    if (this.flashStartedAt === null) {
      if (t >= this.nextFlashAt) this.flashStartedAt = t; else return 0;
    }
    const d = t - this.flashStartedAt;
    if (d < 0.055) return d / 0.055;
    if (d < 0.115) return 1.0 - (d - 0.055) / 0.060 * 0.82;
    if (d < 0.180) return 0.18 + (d - 0.115) / 0.065 * 0.62;
    if (d < 0.340) return 0.80 * (1.0 - (d - 0.180) / 0.160);
    this.flashStartedAt = null;
    this.nextFlashAt = t + 7.0;
    return 0;
  }

  update(t) {
    const a = this.active;
    // mist
    const motionScale = 0.35 + a.mist_motion * 1.35;
    for (const g of this.mistGroups) {
      const { config: c, layerA, layerB } = g.userData;
      const ny = (c.y - 0.12) / (1.18 - 0.12);
      const targetY = lerp(0.08, 1.35 + a.mist_height * 0.9, ny);
      g.visible = a.mist_amount > 0.01;
      g.position.y = targetY + Math.sin(t * 0.22 * motionScale + c.phase) * c.wobble * motionScale;
      layerA.rotation.z = t * c.rotA * motionScale;
      layerB.rotation.z = Math.PI * 0.18 + t * c.rotB * motionScale;
      layerA.material.alphaMap.offset.set(wrapOffset(t * c.speedAX * motionScale), wrapOffset(t * c.speedAZ * motionScale));
      layerB.material.alphaMap.offset.set(wrapOffset(t * c.speedBX * motionScale), wrapOffset(t * c.speedBZ * motionScale));
      layerA.material.opacity = c.opacityA * a.mist_amount;
      layerB.material.opacity = c.opacityB * a.mist_amount;
    }
    // rain
    this.rain.visible = a.rain_amount > 0.01;
    if (this.rain.visible) {
      const visible = Math.round(RAIN_COUNT * a.rain_amount);
      const p = this.rainPositions;
      for (let i = 0; i < RAIN_COUNT; i++) {
        const o = i * 6;
        if (i >= visible) { p.fill(0, o, o + 6); continue; }
        const b = this.rainBase[i];
        const span = 9.6;
        const cy = (b.y0 - t * b.speed) % span;
        const y = cy < 0 ? cy + span : cy;
        p[o] = b.x; p[o + 1] = y; p[o + 2] = b.z;
        p[o + 3] = b.x - 0.05; p[o + 4] = y - b.length; p[o + 5] = b.z + 0.025;
      }
      this.rainAttr.needsUpdate = true;
    }
    // lightning
    const flash = a.lightning_amount > 0.01 ? this.lightningStrength(t) * a.lightning_amount : 0;
    this.dirLight.intensity = this.baseLight + flash * (3.0 + a.lightning_amount * 5.0);
    this.renderer.toneMappingExposure = this.baseExposure + flash * 0.30;
    this.rainMaterial.opacity = a.rain_amount * (0.30 + flash * 0.18);
  }
}
