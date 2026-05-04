// Simplex Noise (Ashima Arts)
const NOISE_GLSL = /* glsl */ `
vec3 mod289(vec3 x){return x-floor(x*(1./289.))*289.;}
vec4 mod289(vec4 x){return x-floor(x*(1./289.))*289.;}
vec4 permute(vec4 x){return mod289(((x*34.)+1.)*x);}
vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-.85373472095314*r;}

float snoise(vec3 v){
  const vec2 C=vec2(1./6.,1./3.);
  const vec4 D=vec4(0.,.5,1.,2.);
  vec3 i=floor(v+dot(v,C.yyy));
  vec3 x0=v-i+dot(i,C.xxx);
  vec3 g=step(x0.yzx,x0.xyz);
  vec3 l=1.-g;
  vec3 i1=min(g.xyz,l.zxy);
  vec3 i2=max(g.xyz,l.zxy);
  vec3 x1=x0-i1+C.xxx;
  vec3 x2=x0-i2+C.yyy;
  vec3 x3=x0-D.yyy;
  i=mod289(i);
  vec4 p=permute(permute(permute(
    i.z+vec4(0.,i1.z,i2.z,1.))
    +i.y+vec4(0.,i1.y,i2.y,1.))
    +i.x+vec4(0.,i1.x,i2.x,1.));
  float n_=.142857142857;
  vec3 ns=n_*D.wyz-D.xzx;
  vec4 j=p-49.*floor(p*ns.z*ns.z);
  vec4 x_=floor(j*ns.z);
  vec4 y_=floor(j-7.*x_);
  vec4 x=x_*ns.x+ns.yyyy;
  vec4 y=y_*ns.x+ns.yyyy;
  vec4 h=1.-abs(x)-abs(y);
  vec4 b0=vec4(x.xy,y.xy);
  vec4 b1=vec4(x.zw,y.zw);
  vec4 s0=floor(b0)*2.+1.;
  vec4 s1=floor(b1)*2.+1.;
  vec4 sh=-step(h,vec4(0.));
  vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy;
  vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;
  vec3 p0=vec3(a0.xy,h.x);
  vec3 p1=vec3(a0.zw,h.y);
  vec3 p2=vec3(a1.xy,h.z);
  vec3 p3=vec3(a1.zw,h.w);
  vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));
  p0*=norm.x;p1*=norm.y;p2*=norm.z;p3*=norm.w;
  vec4 m=max(.6-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.);
  m=m*m;
  return 42.*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));
}
`

export const EGG_VERT = /* glsl */ `
uniform float uTime;
uniform float uGrowth;
uniform float uDissolve;
uniform float uBeat;
uniform float uSeed;
uniform float uShapeType;
uniform float uScaleType;
uniform float uSizeScale;

varying vec3 vNormal;
varying vec3 vWorldPos;
varying vec3 vLocalPos;

${NOISE_GLSL}

vec3 eggDisplace(vec3 pos, vec3 nrm) {
  float y = pos.y;
  float topNarrow = 0.7;
  float widthScale = 1.0;
  float heightScale = 1.3;
  float asymmetry = 0.15;

  if (uShapeType < 0.5) {
    topNarrow = 0.6; widthScale = 1.0; heightScale = 1.1; asymmetry = 0.1;
  } else if (uShapeType < 1.5) {
    topNarrow = 0.65; widthScale = 0.85; heightScale = 1.35; asymmetry = 0.12;
  } else if (uShapeType < 2.5) {
    topNarrow = 0.55; widthScale = 1.15; heightScale = 0.9; asymmetry = 0.18;
  } else if (uShapeType < 3.5) {
    topNarrow = 0.7; widthScale = 0.75; heightScale = 1.6; asymmetry = 0.1;
  } else if (uShapeType < 4.5) {
    topNarrow = 0.8; widthScale = 0.9; heightScale = 1.4; asymmetry = 0.25;
  } else if (uShapeType < 5.5) {
    topNarrow = 0.5; widthScale = 1.1; heightScale = 1.2; asymmetry = 0.2;
  } else if (uShapeType < 6.5) {
    topNarrow = 0.75; widthScale = 1.0; heightScale = 1.5; asymmetry = 0.3;
  } else {
    topNarrow = 0.85; widthScale = 0.7; heightScale = 1.8; asymmetry = 0.15;
  }

  float normalizedY = y / heightScale;
  float topFactor = 1.0 - max(0.0, normalizedY) * topNarrow;
  float bottomBulge = 1.0 + max(0.0, -normalizedY) * asymmetry;
  float radialScale = widthScale * topFactor * bottomBulge;

  vec3 displaced = vec3(pos.x * radialScale, pos.y * heightScale, pos.z * radialScale);

  float n1 = snoise(displaced * 1.8 + uTime * 0.03 + vec3(uSeed)) * 0.015;
  float n2 = snoise(displaced * 3.5 + uTime * 0.05 + vec3(uSeed * 7.13)) * 0.008;
  float heartbeat = uBeat * 0.03;
  float breath = sin(uTime * 0.4) * 0.008;
  float totalDisp = n1 + n2 + heartbeat + breath;

  float scaleBump = 0.0;
  if (uScaleType > 0.5) {
    float scaleNoise = snoise(displaced * (4.0 + uScaleType * 0.5) + vec3(uSeed * 3.0));
    scaleBump = scaleNoise * 0.008 * min(uScaleType / 3.0, 1.0);
  }

  displaced += nrm * (totalDisp + scaleBump);
  float scale = uSizeScale * (0.8 + uGrowth * 0.6);
  displaced *= scale;
  displaced *= 1.0 - uDissolve * 0.3;

  return displaced;
}

void main() {
  vec3 nrm = normalize(normal);
  vec3 pos = eggDisplace(position, nrm);

  vNormal = normalize(normalMatrix * nrm);
  vWorldPos = (modelMatrix * vec4(pos, 1.0)).xyz;
  vLocalPos = position;

  gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
}
`

export const EGG_FRAG = /* glsl */ `
varying vec3 vNormal;
varying vec3 vWorldPos;
varying vec3 vLocalPos;

uniform float uTime;
uniform float uGrowth;
uniform float uDissolve;
uniform float uBeat;
uniform float uSeed;
uniform float uScaleType;
uniform float uMistIntensity;
uniform vec3 uBaseColor;
uniform vec3 uCoreColor;
uniform vec3 uSpecColor;

${NOISE_GLSL}

float scalePattern(vec3 p, float scaleType) {
  if (scaleType < 0.5) return 0.0;

  float pattern = 0.0;

  if (scaleType < 1.5) {
    pattern = snoise(p * 12.0 + vec3(uSeed)) * 0.5 + 0.5;
    pattern = smoothstep(0.4, 0.6, pattern) * 0.15;
  } else if (scaleType < 2.5) {
    float hex = snoise(p * 8.0 + vec3(uSeed));
    float edges = abs(hex);
    pattern = smoothstep(0.02, 0.08, edges) * 0.2;
    pattern = 1.0 - pattern;
    pattern *= 0.15;
  } else if (scaleType < 3.5) {
    vec3 sp = p * 6.0;
    float d = abs(fract(sp.x + sp.y) - 0.5) + abs(fract(sp.y + sp.z) - 0.5);
    pattern = smoothstep(0.3, 0.35, d) * 0.18;
  } else if (scaleType < 4.5) {
    float angle = atan(p.z, p.x);
    float spiral = sin(angle * 3.0 + p.y * 8.0 + uTime * 0.1) * 0.5 + 0.5;
    pattern = spiral * 0.12;
  } else if (scaleType < 5.5) {
    float crack1 = abs(snoise(p * 5.0 + vec3(uSeed)));
    float crack2 = abs(snoise(p * 10.0 + vec3(uSeed * 2.0)));
    pattern = smoothstep(0.0, 0.05, crack1) * 0.1;
    pattern += smoothstep(0.0, 0.03, crack2) * 0.08;
  } else if (scaleType < 6.5) {
    float rune1 = snoise(p * 4.0 + vec3(uSeed));
    float rune2 = snoise(p * 8.0 + vec3(uSeed * 5.0));
    float lines = abs(sin(rune1 * 6.28 + rune2 * 3.14));
    pattern = smoothstep(0.85, 0.95, lines) * 0.25;
  } else {
    float prism = snoise(p * 6.0 + uTime * 0.02 + vec3(uSeed));
    pattern = prism * 0.5 + 0.5;
    pattern *= 0.2;
  }

  return pattern;
}

void main() {
  vec3 V = normalize(cameraPosition - vWorldPos);
  vec3 N = normalize(vNormal);
  float NdV = max(dot(N, V), 0.0);

  vec3 keyDir = normalize(vec3(2.0, 5.0, 4.0));
  float keyDiff = dot(N, keyDir) * 0.5 + 0.5;
  vec3 diffuse = uBaseColor * keyDiff * keyDiff * 0.65;

  vec3 fillDir = normalize(vec3(-3.0, 2.0, -1.0));
  float fillDiff = dot(N, fillDir) * 0.5 + 0.5;
  diffuse += uBaseColor * fillDiff * 0.25;

  float hem = N.y * 0.5 + 0.5;
  vec3 ambient = uBaseColor * mix(0.18, 0.32, hem);

  float pattern = scalePattern(vLocalPos, uScaleType);
  float scaleGlow = pattern * uGrowth * 0.5;
  vec3 patternColor = mix(uBaseColor * (1.0 + pattern * 0.5), uCoreColor, scaleGlow);

  float sss = pow(1.0 - NdV, 2.5);
  vec3 sssGlow = uCoreColor * 0.3 * sss * (0.5 + uGrowth * 0.3);

  float pulse = uBeat;
  float breath = sin(uTime * 0.4) * 0.5 + 0.5;
  float baseIntensity = 0.15 + breath * 0.08 + pulse * 0.25;
  float coreIntensity = baseIntensity + uGrowth * (0.8 + pulse * 0.4);

  float glow = pow(NdV, 2.0);
  float hotspot = pow(NdV, 10.0);
  vec3 core = mix(uCoreColor * 0.3, uCoreColor, hotspot);

  float fresnel = pow(1.0 - NdV, 3.0);
  float mistNoise = snoise(vWorldPos * 2.0 + uTime * 0.15 + vec3(uSeed)) * 0.5 + 0.5;
  float mistAmount = uMistIntensity / 4.0;
  vec3 mist = uCoreColor * fresnel * mistAmount * (0.5 + mistNoise * 0.5);

  float genMist = max(0.0, uGrowth - 1.0) * 0.4;
  mist += uCoreColor * fresnel * genMist * mistNoise;

  vec3 rim = (uBaseColor * 0.3 + vec3(0.05)) * fresnel * (1.0 - mistAmount * 0.5);

  vec3 H1 = normalize(keyDir + V);
  float spec = pow(max(dot(N, H1), 0.0), 80.0) * 0.45;

  vec3 color = ambient + diffuse;
  color = mix(color, patternColor, pattern);
  color += sssGlow;
  color += rim;
  color += mist;
  color += core * glow * coreIntensity;
  color += uSpecColor * spec;

  color = color / (color + vec3(1.0));

  float dissolveNoise = snoise(vLocalPos * 5.0 + vec3(uSeed * 11.0));
  float dissolveThreshold = uDissolve * 2.0 - 1.0;
  if (dissolveNoise < dissolveThreshold) discard;

  float edgeDist = dissolveNoise - dissolveThreshold;
  if (edgeDist < 0.15 && uDissolve > 0.0) {
    color += uCoreColor * 2.0 * (1.0 - edgeDist / 0.15);
  }

  gl_FragColor = vec4(color, 1.0);
}
`

export const EGG_GLOW_VERT = /* glsl */ `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`

export const EGG_GLOW_FRAG = /* glsl */ `
varying vec2 vUv;
uniform float uTime;
uniform float uGrowth;
uniform float uDissolve;
uniform vec3 uGlowColor;
uniform float uMistIntensity;

void main() {
  vec2 center = vUv - 0.5;
  float d = length(center);

  float glow = exp(-d * 3.5) * 0.2;
  float pulse = pow(max(0.0, sin(uTime * (1.0 + uGrowth * 1.5))), 8.0);
  float breath = sin(uTime * 0.4) * 0.5 + 0.5;
  float intensity = (0.15 + breath * 0.06 + pulse * 0.1) + uGrowth * 0.6;

  intensity += uMistIntensity / 4.0 * 0.3;

  vec3 color = mix(uGlowColor * 0.5, uGlowColor, breath) * glow * intensity;
  float alpha = glow * intensity * (1.0 - uDissolve);
  gl_FragColor = vec4(color, alpha);
}
`

export const SHADOW_VERT = /* glsl */ `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`

export const SHADOW_FRAG = /* glsl */ `
varying vec2 vUv;
void main() {
  float d = length(vUv - 0.5) * 2.0;
  float alpha = 0.35 * (1.0 - smoothstep(0.3, 1.0, d));
  vec3 shadowColor = mix(vec3(0.04, 0.02, 0.03), vec3(0.0), d * 0.5);
  gl_FragColor = vec4(shadowColor, alpha);
}
`
