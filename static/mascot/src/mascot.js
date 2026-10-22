// Gaddong(가똥) 마스코트 — Morphloom으로 모델링한 GLB(부품 이름 유지)를 불러와 기분별로 움직인다.
// 빌드: scripts/build_mascot.sh → static/mascot/mascot.bundle.js (window.GaddongMascot)
// 모델 단위는 mm(몸 지름 200), +Y 위, +Z 얼굴 방향.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const TAU = Math.PI * 2;
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

// ---------------- 기분 정의 ----------------
// eyes: 눈 모양 · cheeks: 볼터치(0~1) · bob: 둥실 진폭/속도 · hands: 손 동작 · act: 주기 동작 · fx: 파티클
export const MOODS = {
  ecstatic: { label: '최고예요!', eyes: 'star', cheeks: 1, bob: [7, 2.4], sway: 0.1, hands: 'cheer', act: ['spinJump', 3.0], fx: ['sparkle', 7], props: { star: true }, color: '#ffd76a' },
  happy:    { label: '좋아요!', eyes: 'happy', cheeks: 0.9, bob: [5, 1.8], sway: 0.08, hands: 'clap', act: ['hop', 2.4], fx: ['sparkle', 1.6], color: '#79cfae' },
  proud:    { label: '자신 있어요', eyes: 'happy', cheeks: 0.6, bob: [3, 1.2], sway: 0.04, pitch: -0.14, hands: 'hips', act: ['spin', 5.5], fx: ['sparkle', 0.8], color: '#79cfae' },
  content:  { label: '무난해요', eyes: 'neutral', cheeks: 0.3, bob: [3, 1.1], sway: 0.05, hands: 'rest', act: ['nod', 4.2], fx: null, color: '#b9c2f5' },
  hello:    { label: '무엇이든 물어보세요', eyes: 'neutral', cheeks: 0.5, bob: [3.5, 1.4], sway: 0.05, hands: 'wave', act: ['hop', 4.5], fx: null, color: '#b9c2f5' },
  curious:  { label: '흠, 뭐가 있지?', eyes: 'neutral', cheeks: 0.2, bob: [3, 1.2], sway: 0.03, roll: 0.16, hands: 'hold', act: ['peek', 3.2], fx: ['question', 0.5], props: { magnifier: true }, look: 'wander', color: '#b9c2f5' },
  thinking: { label: '생각 중…', eyes: 'neutral', cheeks: 0.1, bob: [2.5, 0.9], sway: 0.02, roll: -0.1, hands: 'chin', act: ['ponder', 3.6], fx: ['dots', 0.9], props: { magnifier: true }, look: 'up', color: '#c9b8f2' },
  worried:  { label: '아쉬워요…', eyes: 'worried', cheeks: 0, bob: [2, 0.9], sway: 0.03, sink: 8, hands: 'face', act: ['shiver', 3.4], fx: ['sweat', 0.7], color: '#e8c27a' },
  sad:      { label: '속상해요', eyes: 'sad', cheeks: 0, bob: [1.5, 0.7], sway: 0.02, sink: 12, pitch: 0.16, hands: 'down', act: ['sigh', 4.5], fx: ['tear', 0.6], color: '#e58a73' },
  shocked:  { label: '헉! 쇼크예요', eyes: 'ring', cheeks: 0, bob: [2, 3.2], sway: 0, hands: 'cheeks', act: ['jolt', 3.2], fx: ['bang', 0.9], color: '#e58a73' },
  sleepy:   { label: '분석 전이에요 zZ', eyes: 'line', cheeks: 0, bob: [2.5, 0.55], sway: 0.02, sink: 6, pitch: 0.1, hands: 'rest', act: ['sigh', 6], fx: ['zzz', 0.7], color: '#c5c8d1' },
};

// ---------------- 파티클 텍스처 ----------------
function spriteTexture(kind) {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const g = c.getContext('2d');
  g.translate(64, 64);
  if (kind === 'sparkle') {
    const grd = g.createRadialGradient(0, 0, 0, 0, 0, 60);
    grd.addColorStop(0, '#fffbe6'); grd.addColorStop(0.35, '#ffd76a'); grd.addColorStop(1, 'rgba(255,215,106,0)');
    g.fillStyle = grd;
    g.beginPath();
    for (let i = 0; i < 8; i++) {
      const r = i % 2 ? 12 : 60, a = (i * Math.PI) / 4;
      g.lineTo(Math.cos(a) * r, Math.sin(a) * r);
    }
    g.fill();
  } else if (kind === 'sweat' || kind === 'tear') {
    g.fillStyle = kind === 'sweat' ? '#8fc8ff' : '#9fd4ff';
    g.beginPath(); g.moveTo(0, -54); g.bezierCurveTo(40, -6, 34, 46, 0, 48); g.bezierCurveTo(-34, 46, -40, -6, 0, -54); g.fill();
    g.fillStyle = 'rgba(255,255,255,.75)'; g.beginPath(); g.ellipse(-12, 12, 8, 14, -0.4, 0, TAU); g.fill();
  } else {
    const text = { zzz: 'z', question: '?', bang: '!', dots: '…' }[kind];
    g.font = `800 ${kind === 'dots' ? 96 : 104}px Pretendard, system-ui, sans-serif`;
    g.textAlign = 'center'; g.textBaseline = 'middle';
    g.lineWidth = 14; g.strokeStyle = '#ffffff'; g.strokeText(text, 0, 4);
    g.fillStyle = { zzz: '#7d86a8', question: '#4c63f0', bang: '#c23e2c', dots: '#6f5bd6' }[kind];
    g.fillText(text, 0, 4);
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function shadowTexture() {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const g = c.getContext('2d');
  const grd = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  grd.addColorStop(0, 'rgba(40,46,80,.38)'); grd.addColorStop(0.55, 'rgba(40,46,80,.12)'); grd.addColorStop(1, 'rgba(40,46,80,0)');
  g.fillStyle = grd; g.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
}

// ---------------- 눈 모양 ----------------
function eyeShapes(neutralMesh, eyeMat, starMat, glintMat, side) {
  const shapes = {};
  const cap = (r, len) => new THREE.CapsuleGeometry(r, len, 6, 14);
  const group = (...meshes) => { const g = new THREE.Group(); meshes.forEach((m) => g.add(m)); return g; };
  const mesh = (geo, mat = eyeMat) => new THREE.Mesh(geo, mat);

  neutralMesh.position.set(0, 0, 0); neutralMesh.rotation.set(0, 0, 0);
  neutralMesh.material = eyeMat;
  shapes.neutral = group(neutralMesh);

  // ^ 웃는 눈: 위로 볼록한 호 + 둥근 끝
  const arc = (up) => {
    const curve = new THREE.QuadraticBezierCurve3(new THREE.Vector3(-9, up ? -4 : 5, 2), new THREE.Vector3(0, up ? 12 : -10, 2), new THREE.Vector3(9, up ? -4 : 5, 2));
    const tube = mesh(new THREE.TubeGeometry(curve, 24, 2.8, 10, false));
    const a = mesh(new THREE.SphereGeometry(2.8, 12, 8)); a.position.copy(curve.v0);
    const b = mesh(new THREE.SphereGeometry(2.8, 12, 8)); b.position.copy(curve.v2);
    return group(tube, a, b);
  };
  shapes.happy = arc(true);

  // 별 눈
  const star = new THREE.Shape();
  for (let i = 0; i < 10; i++) {
    const r = i % 2 ? 4.6 : 11, a = Math.PI / 2 + (i * Math.PI) / 5;
    i ? star.lineTo(Math.cos(a) * r, Math.sin(a) * r) : star.moveTo(Math.cos(a) * r, Math.sin(a) * r);
  }
  const starGeo = new THREE.ExtrudeGeometry(star, { depth: 2, bevelEnabled: true, bevelSize: 1.2, bevelThickness: 1.2, bevelSegments: 2 });
  shapes.star = group(mesh(starGeo, starMat));

  // O 눈(놀람): 고리 + 작은 동공
  const pupil = mesh(new THREE.SphereGeometry(3.4, 14, 10)); pupil.position.z = 1;
  shapes.ring = group(mesh(new THREE.TorusGeometry(9, 2.6, 10, 32)), pupil);

  // > < 질끈 눈
  const chev = group(mesh(cap(2.5, 11)), mesh(cap(2.5, 11)));
  const s = side === 'left' ? 1 : -1;
  chev.children[0].position.set(-1.5 * s, 4.2, 1); chev.children[0].rotation.z = s * 1.0;
  chev.children[1].position.set(-1.5 * s, -4.2, 1); chev.children[1].rotation.z = -s * 1.0;
  shapes.squeeze = chev;

  // – 감은 눈
  const line = mesh(cap(2.8, 13)); line.rotation.z = Math.PI / 2;
  shapes.line = group(line);

  // 걱정·슬픔: 기본 눈을 안쪽이 올라가게 기울이고 납작하게(눈썹 대신 기울기로 표현)
  const tilted = (k, sy) => { const m = neutralMesh.clone(); m.scale.set(1, sy, 1); m.rotation.z = (side === 'left' ? -1 : 1) * k; return group(m); };
  shapes.worried = tilted(0.42, 0.8);
  shapes.sad = tilted(0.55, 0.62);
  // 캐치라이트(눈 속 하이라이트): 기본·걱정·슬픔·놀람 눈에 붙인다
  const glint = (x, y, z, r) => {
    const m = new THREE.Mesh(new THREE.SphereGeometry(r, 12, 8), glintMat);
    m.position.set(x, y, z); m.scale.z = 0.4;
    return m;
  };
  shapes.neutral.add(glint(-2.4, 8.5, 7.1, 2.7), glint(2.6, -7, 7.0, 1.2));
  shapes.worried.add(glint(-2.2, 6.5, 7.1, 2.4));
  shapes.sad.add(glint(-2.2, 5, 7.1, 2.1));
  shapes.ring.add(glint(-1.6, 1.8, 3.6, 1.4));
  // 눈 피벗은 몸 표면보다 약 3mm 안쪽이다. 새로 만든 모양은 표면 밖으로 띄워야 묻히지 않는다
  for (const k of ['happy', 'star', 'ring', 'squeeze', 'line']) shapes[k].position.z = 4.2;
  return shapes;
}

// ---------------- 손 위치(기분별) ----------------
function handTargets(mode, t, side) {
  const s = side === 'left' ? -1 : 1;
  const rest = new THREE.Vector3(92 * s, -40 + Math.sin(t * 1.7 + (s > 0 ? 0 : 1.4)) * 3, 24);
  switch (mode) {
    case 'cheer': return new THREE.Vector3(98 * s + Math.sin(t * 9 + s) * 6, 52 + Math.sin(t * 9) * 8, 26);
    case 'clap': {
      const k = Math.max(0, Math.sin(t * 2.4)) ** 6;   // 가끔 앞으로 모아 박수
      return rest.clone().lerp(new THREE.Vector3(16 * s, -26, 96), k);
    }
    case 'wave': return s > 0 ? new THREE.Vector3(98 + Math.sin(t * 8) * 10, 34 + Math.cos(t * 8) * 4, 34) : rest;
    case 'hips': return new THREE.Vector3(104 * s, -58, 4);
    case 'face': return new THREE.Vector3(66 * s + Math.sin(t * 6 + s) * 2, -12, 72);
    case 'cheeks': return new THREE.Vector3(76 * s, 6 + Math.sin(t * 30) * 1.5, 62);
    case 'down': return new THREE.Vector3(84 * s, -72, 14);
    case 'chin': return s < 0 ? new THREE.Vector3(-30, -78, 88) : rest;
    case 'hold': return s > 0 ? new THREE.Vector3(104, -18 + Math.sin(t * 1.6) * 4, 58) : rest;
    default: return rest;
  }
}

// ---------------- 주기 동작 ----------------
// 반환: y(위), z(앞), spin(Y축 회전), squash(세로 배율), shake(X 흔들림), pitch, roll
const ACTIONS = {
  hop: { dur: 0.55, f: (t) => ({ y: Math.sin(Math.PI * t) * 20, squash: t < 0.12 || t > 0.9 ? 0.92 : 1.05 }) },
  spinJump: { dur: 1.15, f: (t) => ({ y: Math.sin(Math.PI * t) * 46, spin: ease(t) * TAU, squash: t < 0.1 || t > 0.92 ? 0.88 : 1.06 }) },
  spin: { dur: 1.0, f: (t) => ({ y: Math.sin(Math.PI * t) * 10, spin: ease(t) * TAU }) },
  nod: { dur: 0.9, f: (t) => ({ pitch: Math.sin(t * TAU * 2) * 0.13 * (1 - t) }) },
  peek: { dur: 1.4, f: (t) => ({ roll: Math.sin(Math.PI * t) * 0.22, z: Math.sin(Math.PI * t) * 14 }) },
  ponder: { dur: 2.0, f: (t) => ({ spin: Math.sin(t * TAU) * 0.35 }) },
  shiver: { dur: 0.7, f: (t) => ({ shake: Math.sin(t * 60) * 3 * (1 - t) }) },
  sigh: { dur: 1.6, f: (t) => ({ squash: 1 - Math.sin(Math.PI * t) * 0.05, y: -Math.sin(Math.PI * t) * 4 }) },
  jolt: { dur: 0.75, f: (t) => ({ y: Math.sin(Math.PI * Math.min(1, t * 2.2)) * 16, z: -Math.sin(Math.PI * t) * 14, shake: Math.sin(t * 70) * 6 * (1 - t), squash: t < 0.08 ? 0.85 : 1 }) },
};

class Spring {
  constructor(v = 0, k = 120, d = 14) { this.v = v; this.x = v; this.k = k; this.d = d; }
  step(target, dt) { const a = this.k * (target - this.x) - this.d * this.v; this.v += a * dt; this.x += this.v * dt; return this.x; }
}

// ---------------- 마운트 ----------------
export async function mount(el, opts = {}) {
  const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  const state = { mood: MOODS[opts.mood] ? opts.mood : 'content' };
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' });
  } catch (e) {
    el.innerHTML = opts.fallback || '';
    return null;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.92;
  renderer.domElement.style.cssText = 'display:block;width:100%;height:100%;touch-action:none;cursor:pointer';
  el.style.position = 'relative';
  el.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.42;
  const key = new THREE.DirectionalLight(0xffffff, 1.35); key.position.set(-260, 420, 520); scene.add(key);
  const rim = new THREE.DirectionalLight(0xc9d2ff, 1.1); rim.position.set(320, 120, -380); scene.add(rim);
  scene.add(new THREE.HemisphereLight(0xf4f5ff, 0xb9bed6, 0.5));

  const camera = new THREE.PerspectiveCamera(26, 1, 10, 4000);
  const framing = opts.framing ?? 1;   // 1 = 손·머리 위 여유 포함
  const fit = () => {
    const w = el.clientWidth || 120, h = el.clientHeight || 120;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    const halfH = 176 * framing, halfW = 150 * framing;   // 머리 위 별(점프 포함)과 바닥 그림자까지
    const dist = Math.max(halfH / Math.tan(THREE.MathUtils.degToRad(13)), halfW / (Math.tan(THREE.MathUtils.degToRad(13)) * camera.aspect));
    camera.position.set(0, 30, dist);
    camera.lookAt(0, 18, 0);
    camera.updateProjectionMatrix();
  };

  // 모델
  const gltf = await new GLTFLoader().parseAsync(opts.glb, '');
  const nodes = {};
  // glTF는 미터 단위로 내보내진다(몸 반지름 0.1). 이 파일의 좌표는 모두 mm라 1000배로 맞춘다.
  gltf.scene.traverse((o) => {
    if (o.isMesh) o.geometry.scale(1000, 1000, 1000);
    if (o !== gltf.scene) o.position.multiplyScalar(1000);
    if (o.name) nodes[o.name] = o;
  });
  const need = ['body', 'eye-left', 'eye-right', 'hand-left', 'hand-right', 'cheek-left', 'cheek-right'];
  if (need.some((n) => !nodes[n])) throw new Error('mascot GLB is missing named parts');
  const meshOf = (o) => (o.isMesh ? o : o.getObjectByProperty('isMesh', true));

  const root = new THREE.Group(); scene.add(root);
  const bodyPivot = new THREE.Group(); root.add(bodyPivot);
  const body = meshOf(nodes.body); body.removeFromParent(); body.position.set(0, 0, 0); bodyPivot.add(body);
  const bodyMat = body.material;
  let hands0Tint = null;
  // 몸 색: 컨콜 톤 색(hue)이 있으면 그 색, 없으면 대시보드 포인트 색(페리윙클) 쪽으로 물들인다
  bodyMat.color.lerp(new THREE.Color().setHSL((opts.hue ?? 232) / 360, 0.8, 0.7), 0.62);
  if (bodyMat.sheenColor) { bodyMat.sheenColor.copy(bodyMat.color); bodyMat.sheen = 0.2; }   // 흰 광택(sheen)이 색을 씻어내지 않게
  hands0Tint = bodyMat.color.clone();

  const face = new THREE.Group(); bodyPivot.add(face);   // 몸 중심이 피벗 → 돌리면 눈이 구면을 따라 미끄러진다(시선)
  // 짙은 유광 눈 + 흰 캐치라이트: 밝은 몸 위에서 또렷하게 보인다
  const eyeMat = new THREE.MeshPhysicalMaterial({ color: 0x1b1e2e, roughness: 0.14, clearcoat: 1, clearcoatRoughness: 0.04 });
  const glintMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
  const starMat = new THREE.MeshPhysicalMaterial({ color: 0xffe08a, emissive: 0xffc94a, emissiveIntensity: 0.7, roughness: 0.25, metalness: 0.3, clearcoat: 1 });
  const eyes = ['left', 'right'].map((side) => {
    const src = nodes[`eye-${side}`];
    const rig = new THREE.Group();
    rig.position.copy(src.position); rig.quaternion.copy(src.quaternion);
    const inner = new THREE.Group(); rig.add(inner);
    const shapes = eyeShapes(meshOf(src), eyeMat, starMat, glintMat, side);
    Object.values(shapes).forEach((g) => { g.visible = false; inner.add(g); });
    face.add(rig);
    return { rig, inner, shapes, cur: null };
  });
  const cheeks = ['left', 'right'].map((side) => {
    const m = meshOf(nodes[`cheek-${side}`]);
    const n = nodes[`cheek-${side}`];
    m.removeFromParent(); m.position.copy(n.position); m.quaternion.copy(n.quaternion); m.scale.copy(n.scale);
    m.material = m.material.clone(); m.material.transparent = true; m.material.opacity = 0;
    face.add(m);
    return m;
  });
  const hands = ['left', 'right'].map((side) => {
    const m = meshOf(nodes[`hand-${side}`]);
    m.removeFromParent(); root.add(m);
    m.material.color.copy(hands0Tint);   // 손도 몸과 같은 색
    return { m, side, pos: new THREE.Vector3(92 * (side === 'left' ? -1 : 1), -40, 24) };
  });
  // 소품: 별(머리 위), 돋보기(오른손)
  const star = new THREE.Group();
  if (nodes['prop-star']) {
    const s = meshOf(nodes['prop-star']); s.removeFromParent(); s.position.set(0, 0, -2.5);
    s.material = starMat;   // 금속 금색은 어두운 환경에서 갈색으로 보여 스스로 빛나는 금색으로
    star.add(s);
  }
  star.position.set(0, 132, 0); star.scale.setScalar(0.001); root.add(star);
  const magnifier = new THREE.Group();
  ['prop-magnifier-ring', 'prop-magnifier-lens', 'prop-magnifier-handle'].forEach((n) => {
    if (!nodes[n]) return;
    const src = nodes[n], m = meshOf(src);
    m.removeFromParent(); m.position.copy(src.position).sub(new THREE.Vector3(150, 10, 40)); m.quaternion.copy(src.quaternion);
    magnifier.add(m);
  });
  magnifier.scale.setScalar(0.001); root.add(magnifier);

  const shadow = new THREE.Mesh(new THREE.PlaneGeometry(240, 240), new THREE.MeshBasicMaterial({ map: shadowTexture(), transparent: true, depthWrite: false }));
  shadow.rotation.x = -Math.PI / 2; shadow.position.y = -128; scene.add(shadow);

  // 파티클
  const fxTex = {};
  const particles = [];
  const fxGroup = new THREE.Group(); scene.add(fxGroup);
  function emit(kind) {
    fxTex[kind] ??= spriteTexture(kind);
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: fxTex[kind], transparent: true, depthWrite: false }));
    const p = { sp, kind, life: 0, max: 1.6, vel: new THREE.Vector3() };
    const y0 = root.position.y;
    if (kind === 'sparkle') { const a = Math.random() * TAU; sp.position.set(Math.cos(a) * 125, y0 + 20 + Math.random() * 110, Math.sin(a) * 40 + 40); p.vel.set(0, 18, 0); p.max = 1.1; p.size = 22 + Math.random() * 16; }
    else if (kind === 'sweat') { sp.position.set(62, y0 + 62, 70); p.vel.set(6, -26, 0); p.max = 1.3; p.size = 20; }
    else if (kind === 'tear') { const s = Math.random() < 0.5 ? -1 : 1; sp.position.set(22 * s, y0 - 6, 98); p.vel.set(4 * s, -60, 4); p.max = 1.0; p.size = 13; }
    else if (kind === 'zzz') { sp.position.set(70, y0 + 80, 30); p.vel.set(24, 34, 0); p.max = 2.2; p.size = 26 + Math.random() * 12; }
    else if (kind === 'question') { sp.position.set(-80 + Math.random() * 20, y0 + 118, 20); p.vel.set(-4, 16, 0); p.max = 1.8; p.size = 40; }
    else if (kind === 'bang') { const s = Math.random() < 0.5 ? -1 : 1; sp.position.set(96 * s, y0 + 96, 20); p.vel.set(10 * s, 26, 0); p.max = 0.9; p.size = 40; }
    else if (kind === 'dots') { sp.position.set(84, y0 + 112, 20); p.vel.set(6, 10, 0); p.max = 1.7; p.size = 46; }
    sp.scale.setScalar(0.01);
    fxGroup.add(sp); particles.push(p);
  }

  // 말풍선
  let bubble = null;
  if (opts.bubble !== false) {
    bubble = document.createElement('div');
    bubble.style.cssText = 'position:absolute;left:50%;top:2px;transform:translate(-50%,-4px) scale(.9);opacity:0;pointer-events:none;'
      + 'font:700 11px/1.2 Pretendard,system-ui,sans-serif;color:#12141A;background:rgba(255,255,255,.92);border:1px solid rgba(18,20,26,.08);'
      + 'box-shadow:0 6px 16px -8px rgba(40,52,140,.35);padding:4px 8px;border-radius:999px;white-space:nowrap;transition:opacity .25s,transform .35s cubic-bezier(.16,1,.3,1)';
    el.appendChild(bubble);
  }
  let bubbleTimer = 0;
  const say = (text, sec = 2.6) => {
    if (!bubble) return;
    bubble.textContent = text; bubble.style.opacity = '1'; bubble.style.transform = 'translate(-50%,0) scale(1)';
    bubbleTimer = sec;
  };

  // 상태
  const sp = { y: new Spring(0, 90, 13), z: new Spring(0, 90, 13), spin: new Spring(0, 70, 12), yaw: new Spring(0, 40, 10), pitch: new Spring(0, 40, 10),
    roll: new Spring(0, 40, 10), sq: new Spring(1, 220, 14), lookX: new Spring(0, 60, 11), lookY: new Spring(0, 60, 11), cheek: new Spring(0, 30, 9),
    star: new Spring(0, 120, 12), mag: new Spring(0, 120, 12), blink: new Spring(1, 600, 30) };
  let action = null, actT = 0, nextAct = 1.2, fxAcc = 0, nextBlink = 2 + Math.random() * 2, override = null, overrideT = 0, eyeSwitch = null;
  const pointer = { on: false, x: 0, y: 0 };

  function setEyes(shape, instant = false) {
    eyes.forEach((e) => {
      if (e.cur === shape) return;
      if (instant || !e.cur) { Object.entries(e.shapes).forEach(([k, g]) => { g.visible = k === shape; }); e.cur = shape; }
    });
    if (!instant && eyes[0].cur !== shape) eyeSwitch = { to: shape, t: 0 };   // 깜빡이며 바꾼다
  }
  function setMood(m, announce = true) {
    if (!MOODS[m]) return;
    state.mood = m;
    setEyes(MOODS[m].eyes, eyes[0].cur == null);
    action = null; nextAct = 0.6;
    if (announce) say(opts.label || MOODS[m].label);
  }
  setMood(state.mood, false);
  if (opts.greet !== false) setTimeout(() => say(opts.label || MOODS[state.mood].label, 3.2), 350);

  // 입력
  const cv = renderer.domElement;
  cv.addEventListener('pointermove', (ev) => {
    const r = cv.getBoundingClientRect();
    pointer.on = true; pointer.x = ((ev.clientX - r.left) / r.width) * 2 - 1; pointer.y = -(((ev.clientY - r.top) / r.height) * 2 - 1);
  });
  cv.addEventListener('pointerenter', () => { pointer.on = true; if (!override) say(opts.label || MOODS[state.mood].label, 2); });
  cv.addEventListener('pointerleave', () => { pointer.on = false; });
  const reactions = [['happy', '헤헤', 'spinJump'], ['ecstatic', '간지러워요!', 'spin'], ['happy', '안녕하세요!', 'hop']];
  let poke = 0;
  cv.addEventListener('click', () => {
    const [eyesKey, text, act] = reactions[poke++ % reactions.length];
    override = eyesKey; overrideT = 1.4; setEyes(MOODS[eyesKey].eyes);
    action = act; actT = 0; say(text, 1.6);
    for (let i = 0; i < 6; i++) emit('sparkle');
  });

  // 루프
  let visible = true, last = performance.now(), t = 0, raf = 0;
  const io = new IntersectionObserver((es) => { visible = es[0].isIntersecting; }, { threshold: 0.01 });
  io.observe(el);
  const ro = new ResizeObserver(fit); ro.observe(el); fit();

  function frame(now) {
    raf = requestAnimationFrame(frame);
    if (!visible || document.hidden) { last = now; return; }
    const dt = Math.min(0.05, (now - last) / 1000); last = now; t += dt;
    const M = MOODS[override || state.mood];
    const base = MOODS[state.mood];
    const calm = reduce ? 0.15 : 1;

    // 주기 동작
    if (!reduce) {
      nextAct -= dt;
      if (!action && nextAct <= 0) { action = base.act?.[0] || null; actT = 0; nextAct = (base.act?.[1] || 4) * (0.8 + Math.random() * 0.45); }
    }
    let a = {};
    if (action && ACTIONS[action]) {
      actT += dt / ACTIONS[action].dur;
      a = ACTIONS[action].f(Math.min(1, actT));
      if (actT >= 1) { action = null; a = {}; }
      if (state.mood === 'shocked' && actT > 0.15 && actT < 0.5 && !override) setEyes('squeeze', true);
      else if (state.mood === 'shocked' && !override && eyes[0].cur === 'squeeze' && actT >= 0.5) setEyes('ring', true);
    }

    // 눈 바꾸기(깜빡이며)
    let blinkTarget = 1;
    if (eyeSwitch) {
      eyeSwitch.t += dt;
      blinkTarget = eyeSwitch.t < 0.09 ? 0.05 : 1;
      if (eyeSwitch.t >= 0.09 && eyes[0].cur !== eyeSwitch.to) eyes.forEach((e) => { Object.entries(e.shapes).forEach(([k, g]) => { g.visible = k === eyeSwitch.to; }); e.cur = eyeSwitch.to; });
      if (eyeSwitch.t > 0.3) eyeSwitch = null;
    } else if (['neutral', 'ring', 'worried', 'sad'].includes(eyes[0].cur)) {
      nextBlink -= dt;
      if (nextBlink < 0) { blinkTarget = 0.05; if (nextBlink < -0.11) nextBlink = 2.2 + Math.random() * 3.2 * (state.mood === 'sleepy' ? 0.4 : 1); }
    }
    const bl = sp.blink.step(blinkTarget, dt);
    eyes.forEach((e) => { e.inner.scale.y = clamp(bl, 0.04, 1.2); });

    if (override) { overrideT -= dt; if (overrideT <= 0) { override = null; setEyes(base.eyes); } }

    // 몸
    const bob = Math.sin(t * TAU * (M.bob?.[1] || 1) * 0.5) * (M.bob?.[0] || 2) * calm;
    root.position.y = sp.y.step((a.y || 0) * calm + bob - (M.sink || 0), dt);
    root.position.z = sp.z.step((a.z || 0) * calm, dt);
    root.position.x = (a.shake || 0) * calm;
    const spinT = (a.spin || 0) * calm;
    root.rotation.y = action === 'spinJump' || action === 'spin' ? spinT : sp.spin.step(spinT, dt);
    const sway = Math.sin(t * 1.3) * (M.sway || 0) * calm;
    let yaw = sway, pitch = (M.pitch || 0) + (a.pitch || 0), roll = (M.roll ? Math.sin(t * 0.8) * M.roll : 0) + (a.roll || 0);
    if (pointer.on) { yaw += pointer.x * 0.35; pitch += -pointer.y * 0.22; }
    bodyPivot.rotation.set(sp.pitch.step(pitch, dt), sp.yaw.step(yaw, dt), sp.roll.step(roll * calm, dt));
    const sq = sp.sq.step(a.squash || 1, dt);
    bodyPivot.scale.set(1 / Math.sqrt(sq), sq, 1 / Math.sqrt(sq));

    // 시선: 얼굴 그룹을 구 위에서 미끄러뜨린다
    let lx = 0, ly = 0;
    if (pointer.on) { lx = pointer.x * 0.28; ly = pointer.y * 0.2; }
    else if (M.look === 'wander') { lx = Math.sin(t * 0.9) * 0.3; ly = Math.sin(t * 0.6) * 0.08; }
    else if (M.look === 'up') { lx = 0.2; ly = 0.22; }
    else if (state.mood === 'worried') { lx = Math.sin(t * 0.7) * 0.18; ly = -0.06; }
    face.rotation.set(-sp.lookY.step(ly, dt), sp.lookX.step(lx, dt), 0);

    // 볼터치·색
    const ck = sp.cheek.step(M.cheeks || 0, dt);
    cheeks.forEach((c) => { c.material.opacity = ck * 0.85; c.visible = ck > 0.02; });

    // 손
    hands.forEach((h) => {
      const target = handTargets(reduce ? 'rest' : M.hands, t, h.side);
      h.pos.lerp(target, 1 - Math.exp(-dt * 9));
      h.m.position.copy(h.pos);
      const sqh = 1 + Math.sin(t * 3 + (h.side === 'left' ? 0 : 2)) * 0.02;
      h.m.scale.set(sqh, 1 / sqh, sqh);
    });

    // 소품
    const showStar = (M.props?.star ? 1 : 0), showMag = (M.props?.magnifier ? 1 : 0);
    star.scale.setScalar(Math.max(0.001, sp.star.step(showStar, dt)));
    star.rotation.y = t * 2.4; star.position.y = 132 + Math.sin(t * 3) * 5;
    magnifier.scale.setScalar(Math.max(0.001, sp.mag.step(showMag, dt)));
    const rh = hands[1].m.position;
    magnifier.position.set(rh.x + 24, rh.y + 30, rh.z + 6);
    magnifier.rotation.set(0, -0.35 + Math.sin(t * 1.2) * 0.25, Math.sin(t * 0.9) * 0.12);

    // 그림자: 높이 뜰수록 작고 옅게
    const hgt = clamp((root.position.y + 20) / 80, 0, 1);
    shadow.scale.setScalar(1 - hgt * 0.35);
    shadow.material.opacity = 1 - hgt * 0.55;

    // 파티클
    if (M.fx && !reduce) {
      fxAcc += dt * M.fx[1];
      while (fxAcc > 1) { fxAcc -= 1; emit(M.fx[0]); }
    }
    for (let i = particles.length - 1; i >= 0; i--) {
      const p = particles[i];
      p.life += dt;
      const k = p.life / p.max;
      if (k >= 1) { fxGroup.remove(p.sp); p.sp.material.dispose(); particles.splice(i, 1); continue; }
      p.sp.position.addScaledVector(p.vel, dt);
      const pop = k < 0.2 ? k / 0.2 : 1;
      p.sp.scale.setScalar(p.size * pop * (p.kind === 'sparkle' ? 1 - k * 0.5 : 1));
      p.sp.material.opacity = k > 0.6 ? (1 - k) / 0.4 : 1;
      if (p.kind === 'sparkle') p.sp.material.rotation += dt * 2;
    }

    if (bubble && bubbleTimer > 0) { bubbleTimer -= dt; if (bubbleTimer <= 0) { bubble.style.opacity = '0'; bubble.style.transform = 'translate(-50%,-4px) scale(.9)'; } }
    renderer.render(scene, camera);
  }
  raf = requestAnimationFrame(frame);

  return {
    setMood,
    say,
    destroy() { cancelAnimationFrame(raf); io.disconnect(); ro.disconnect(); renderer.dispose(); el.innerHTML = ''; },
  };
}


// iframe에서 쓰는 진입점: GLB를 받아 마운트한다. 실패하면 CSS 오브(fallback)로 돌아간다.
export async function boot(el, opts = {}) {
  try {
    const res = await fetch(opts.glbUrl, { cache: 'force-cache' });
    if (!res.ok) throw new Error(`GLB ${res.status}`);
    return await mount(el, { ...opts, glb: await res.arrayBuffer() });
  } catch (e) {
    console.warn('[GaddongMascot]', e);
    el.innerHTML = opts.fallback || '';
    return null;
  }
}
