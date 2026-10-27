// Shared GLB loading with the production renderer's normalisation:
// longest bounding-box side -> target size, then rest on y = 0
// (index.html normalizeAndAddModel / applyRotationAndRest).
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';

const loader = new GLTFLoader();
const cache = new Map();

export function loadGLB(slug) {
  if (!cache.has(slug)) {
    cache.set(slug, new Promise((resolve, reject) => {
      loader.load(`/media/glb/${slug}.glb`, (g) => resolve(g.scene), undefined, reject);
    }));
  }
  return cache.get(slug).then((s) => s.clone(true));
}

export function normalise(obj, targetSize = 1) {
  obj.scale.setScalar(1);
  obj.position.set(0, 0, 0);
  obj.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(obj);
  const size = box.getSize(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z) || 1;
  obj.scale.setScalar(targetSize / maxDim);
  obj.updateMatrixWorld(true);
  const b2 = new THREE.Box3().setFromObject(obj);
  const c = b2.getCenter(new THREE.Vector3());
  obj.position.x -= c.x;
  obj.position.z -= c.z;
  obj.position.y -= b2.min.y;
  obj.traverse((n) => { if (n.isMesh) { n.castShadow = true; n.receiveShadow = true; } });
  return obj;
}

export function disposeTree(obj) {
  obj.traverse((n) => {
    if (n.isMesh) {
      n.geometry?.dispose();
      const mats = Array.isArray(n.material) ? n.material : [n.material];
      mats.forEach((m) => m?.dispose());
    }
  });
}
