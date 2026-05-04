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
uniform float uMorph; // 0 = sphere, 1 = full egg shape
varying vec3 vNormal;
varying vec3 vWorldPos;
varying vec3 vLocalPos;
varying float vAO; // ambient occlusion from scale grooves

${NOISE_GLSL}

vec3 eggDisplace(vec3 pos, vec3 nrm) {
  float y = pos.y;

  // Shape parameters: topNarrow, widthScale, heightScale, asymmetry, bellyPos, tipSharpness
  float topNarrow = 0.7;
  float widthScale = 1.0;
  float heightScale = 1.3;
  float asymmetry = 0.15;
  float bellyPos = 0.0;      // vertical offset of widest point (-1 to 1)
  float tipSharpness = 1.0;  // how pointed the top is (higher = sharper)

  if (uShapeType < 0.5) {
    // Round — classic egg, soft and familiar
    topNarrow = 0.38; widthScale = 1.05; heightScale = 1.25; asymmetry = 0.12;
    bellyPos = -0.05; tipSharpness = 1.1;
  } else if (uShapeType < 1.5) {
    // Oval — slightly elongated, elegant
    topNarrow = 0.44; widthScale = 0.95; heightScale = 1.4; asymmetry = 0.08;
    bellyPos = -0.1; tipSharpness = 1.3;
  } else if (uShapeType < 2.5) {
    // Squat — wider and stubbier, but still clearly an egg
    topNarrow = 0.45; widthScale = 1.15; heightScale = 1.1; asymmetry = 0.18;
    bellyPos = -0.1; tipSharpness = 0.9;
  } else if (uShapeType < 3.5) {
    // Elongated — tall and slender
    topNarrow = 0.5; widthScale = 0.82; heightScale = 1.6; asymmetry = 0.05;
    bellyPos = -0.15; tipSharpness = 1.5;
  } else if (uShapeType < 4.5) {
    // Teardrop — bottom-heavy with pointed top
    topNarrow = 0.65; widthScale = 1.0; heightScale = 1.35; asymmetry = 0.3;
    bellyPos = -0.3; tipSharpness = 2.2;
  } else if (uShapeType < 5.5) {
    // Bulbous — plump with character
    topNarrow = 0.32; widthScale = 1.12; heightScale = 1.18; asymmetry = 0.25;
    bellyPos = -0.2; tipSharpness = 0.7;
  } else if (uShapeType < 6.5) {
    // Gourd — dramatic bottom, pinched upper
    topNarrow = 0.7; widthScale = 0.98; heightScale = 1.4; asymmetry = 0.38;
    bellyPos = -0.35; tipSharpness = 2.0;
  } else {
    // Spire — tall and striking, crystal-like
    topNarrow = 0.55; widthScale = 0.72; heightScale = 1.75; asymmetry = 0.02;
    bellyPos = -0.1; tipSharpness = 2.5;
  }

  // Lerp shape parameters from sphere based on morph
  topNarrow *= uMorph;
  widthScale = mix(1.0, widthScale, uMorph);
  heightScale = mix(1.0, heightScale, uMorph);
  asymmetry *= uMorph;
  bellyPos *= uMorph;
  tipSharpness = mix(1.0, tipSharpness, uMorph);

  // Advanced egg profile with belly offset and tip sharpness
  float normalizedY = (y - bellyPos * 0.3) / heightScale;
  float topCurve = pow(cos(clamp(normalizedY, 0.0, 1.0) * 1.5708), tipSharpness) * topNarrow + (1.0 - topNarrow);
  float bottomCurve = 1.0 + pow(sin(clamp(-normalizedY, 0.0, 1.0) * 1.5708), 0.8) * asymmetry;
  float radialScale = widthScale * topCurve * bottomCurve;

  vec3 displaced = vec3(pos.x * radialScale, pos.y * heightScale, pos.z * radialScale);

  // Multi-octave organic surface displacement
  float n1 = snoise(displaced * 2.0 + uTime * 0.02 + vec3(uSeed)) * 0.012;
  float n2 = snoise(displaced * 4.5 + uTime * 0.04 + vec3(uSeed * 7.13)) * 0.006;
  float n3 = snoise(displaced * 9.0 + vec3(uSeed * 13.7)) * 0.003; // fine grain
  float breath = sin(uTime * 0.35) * 0.006;
  float totalDisp = (n1 + n2 + n3) * uMorph + breath;

  // Scale-type surface bump (higher fidelity per type)
  float scaleBump = 0.0;
  if (uScaleType > 0.5) {
    float freq = 4.0 + uScaleType * 0.8;
    float scaleN1 = snoise(displaced * freq + vec3(uSeed * 3.0));
    float scaleN2 = snoise(displaced * freq * 2.2 + vec3(uSeed * 5.7));
    scaleBump = (scaleN1 * 0.7 + scaleN2 * 0.3) * 0.012 * min(uScaleType / 3.0, 1.0) * uMorph;
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

  // Compute AO from scale grooves
  float scaleAO = 0.0;
  if (uScaleType > 0.5) {
    float freq = 4.0 + uScaleType * 0.8;
    float groove = snoise(position * freq + vec3(uSeed * 3.0));
    scaleAO = smoothstep(0.0, 0.2, abs(groove)) * 0.3 * uMorph;
  }

  vAO = 1.0 - scaleAO;
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
varying float vAO;

uniform float uTime;
uniform float uGrowth;
uniform float uDissolve;
uniform float uBeat;
uniform float uSeed;
uniform float uScaleType;
uniform float uMistIntensity;
uniform float uMorph;
uniform vec3 uBaseColor;
uniform vec3 uCoreColor;
uniform vec3 uSpecColor;

${NOISE_GLSL}

// GGX specular distribution
float GGX(float NdH, float roughness) {
  float a = roughness * roughness;
  float a2 = a * a;
  float denom = NdH * NdH * (a2 - 1.0) + 1.0;
  return a2 / (3.14159 * denom * denom + 0.0001);
}

// Fresnel-Schlick approximation
vec3 fresnelSchlick(float cosTheta, vec3 F0) {
  return F0 + (1.0 - F0) * pow(1.0 - cosTheta, 5.0);
}

// Multi-layered scale pattern with depth info
// Returns: x = pattern intensity, y = groove depth, z = highlight
vec3 scalePattern(vec3 p, float scaleType) {
  if (scaleType < 0.5) return vec3(0.0);

  vec3 result = vec3(0.0);

  if (scaleType < 1.5) {
    // Stippled — fine organic bumps, like reptile skin
    float n1 = snoise(p * 18.0 + vec3(uSeed));
    float n2 = snoise(p * 32.0 + vec3(uSeed * 2.3));
    float bumps = n1 * 0.6 + n2 * 0.4;
    float ridge = smoothstep(0.1, 0.4, bumps);
    float groove = smoothstep(-0.1, -0.3, bumps);
    result = vec3(ridge * 0.2, groove * 0.3, ridge * 0.15);
  } else if (scaleType < 2.5) {
    // Hexscale — tessellated plates with visible grooves
    // Use Voronoi-like pattern via noise
    float n1 = snoise(p * 10.0 + vec3(uSeed));
    float n2 = snoise(p * 10.0 + vec3(uSeed + 100.0));
    float voronoi = length(vec2(n1, n2));
    float edges = smoothstep(0.25, 0.35, voronoi);
    float plateCenter = 1.0 - edges;
    float grooveDepth = (1.0 - edges) * 0.0 + edges * 0.4;
    // Slight convexity on each plate
    float highlight = plateCenter * plateCenter * 0.2;
    result = vec3(plateCenter * 0.15, grooveDepth, highlight);
  } else if (scaleType < 3.5) {
    // Diamond — interlocking faceted pattern
    vec3 sp = p * 8.0;
    float d1 = abs(fract(sp.x + sp.y * 0.5) - 0.5);
    float d2 = abs(fract(sp.y + sp.z * 0.5) - 0.5);
    float diamond = min(d1, d2);
    float edge = smoothstep(0.05, 0.12, diamond);
    float facetAngle = fract(sp.x * 0.7 + sp.z * 1.3 + sp.y * 0.4);
    float highlight = pow(facetAngle, 3.0) * edge * 0.3;
    result = vec3(edge * 0.18, (1.0 - edge) * 0.35, highlight);
  } else if (scaleType < 4.5) {
    // Spiral — organic flowing ridges wrapping the egg
    float angle = atan(p.z, p.x);
    float spiral1 = sin(angle * 4.0 + p.y * 10.0 + uTime * 0.05) * 0.5 + 0.5;
    float spiral2 = sin(angle * 7.0 - p.y * 6.0 + 1.5) * 0.5 + 0.5;
    float combined = spiral1 * 0.7 + spiral2 * 0.3;
    float ridge = smoothstep(0.5, 0.8, combined);
    float groove = smoothstep(0.5, 0.2, combined);
    result = vec3(ridge * 0.2, groove * 0.25, ridge * 0.18);
  } else if (scaleType < 5.5) {
    // Cracked — fractured surface with deep fissures
    float crack1 = abs(snoise(p * 6.0 + vec3(uSeed)));
    float crack2 = abs(snoise(p * 12.0 + vec3(uSeed * 2.0)));
    float crack3 = abs(snoise(p * 24.0 + vec3(uSeed * 4.0)));
    float cracks = min(crack1, min(crack2 * 0.8 + 0.1, crack3 * 0.6 + 0.2));
    float edge = smoothstep(0.0, 0.08, cracks);
    float deepCrack = smoothstep(0.08, 0.0, cracks);
    // Plates between cracks catch light
    float plateHighlight = edge * edge * 0.2;
    result = vec3(edge * 0.12, deepCrack * 0.5, plateHighlight);
  } else if (scaleType < 6.5) {
    // Runic — glowing carved symbols
    float rune1 = snoise(p * 4.5 + vec3(uSeed));
    float rune2 = snoise(p * 9.0 + vec3(uSeed * 5.0));
    float lines = abs(sin(rune1 * 6.28 + rune2 * 3.14));
    float carving = smoothstep(0.88, 0.96, lines);
    // Runes glow with core color
    float glowPulse = 0.7 + sin(uTime * 0.8 + rune1 * 3.0) * 0.3;
    result = vec3(carving * 0.35 * glowPulse, carving * 0.2, 0.0);
  } else {
    // Prismatic — iridescent shifting facets
    float prism1 = snoise(p * 7.0 + uTime * 0.015 + vec3(uSeed));
    float prism2 = snoise(p * 14.0 + vec3(uSeed * 3.0));
    float facet = abs(prism1) * 0.6 + abs(prism2) * 0.4;
    float edge = smoothstep(0.05, 0.15, facet);
    float shimmer = pow(sin(prism1 * 12.0 + uTime * 0.3) * 0.5 + 0.5, 2.0);
    result = vec3(edge * 0.15 + shimmer * 0.12, (1.0 - edge) * 0.2, shimmer * 0.3);
  }

  return result;
}

void main() {
  vec3 V = normalize(cameraPosition - vWorldPos);
  vec3 N = normalize(vNormal);
  float NdV = max(dot(N, V), 0.0);

  // ── Surface color variation — makes the egg look deep and rich ──
  // Vertical gradient: darker at base, richer at crown
  float heightGrad = vLocalPos.y * 0.5 + 0.5; // 0 at bottom, 1 at top
  // Noise-based color variation across surface (like mineral veining)
  float colorNoise1 = snoise(vLocalPos * 2.5 + vec3(uSeed * 1.3)) * 0.5 + 0.5;
  float colorNoise2 = snoise(vLocalPos * 5.0 + vec3(uSeed * 7.7)) * 0.5 + 0.5;

  // Create a rich base that varies across the surface
  vec3 darkBase = uBaseColor * 0.6; // deep shadow tone
  vec3 richBase = uBaseColor * 1.2 + uCoreColor * 0.08; // enriched highlights
  vec3 surfaceColor = mix(darkBase, richBase, heightGrad * 0.5 + colorNoise1 * 0.5);
  // Subtle veining toward core color in streaks
  surfaceColor = mix(surfaceColor, uBaseColor * 0.8 + uCoreColor * 0.15, colorNoise2 * 0.25);

  // ── Lighting setup — dramatic 3-point for precious objects ──
  vec3 keyDir = normalize(vec3(2.0, 4.5, 3.5));
  vec3 fillDir = normalize(vec3(-2.5, 1.0, -1.5));
  vec3 backDir = normalize(vec3(0.5, -0.5, -3.0));

  float keyDiff = max(dot(N, keyDir), 0.0);
  float fillDiff = max(dot(N, fillDir), 0.0);
  float backDiff = max(dot(N, backDir), 0.0);

  // Wrap lighting for soft organic material
  float keyWrap = dot(N, keyDir) * 0.5 + 0.5;
  float fillWrap = dot(N, fillDir) * 0.5 + 0.5;

  // Diffuse with color — key light slightly warm, fill slightly cool
  vec3 keyColor = surfaceColor * vec3(1.05, 1.0, 0.95); // warm tint
  vec3 fillColor = surfaceColor * vec3(0.92, 0.95, 1.05); // cool tint
  vec3 diffuse = keyColor * pow(keyWrap, 1.5) * 0.6 + fillColor * fillWrap * 0.2;

  // Hemisphere ambient — sky/ground with material color
  float hem = N.y * 0.5 + 0.5;
  vec3 skyAmb = surfaceColor * 1.1 + vec3(0.015, 0.02, 0.035);
  vec3 gndAmb = surfaceColor * 0.4 + vec3(0.01, 0.005, 0.0);
  vec3 ambient = mix(gndAmb, skyAmb, hem) * 0.35 * vAO;

  // ── Scale pattern ──
  vec3 scaleInfo = scalePattern(vLocalPos, uScaleType) * uMorph;
  float scaleIntensity = scaleInfo.x;
  float scaleGroove = scaleInfo.y;
  float scaleHighlight = scaleInfo.z;

  // Scale pattern modulates the surface color with depth
  vec3 scaleColor = surfaceColor * (1.0 + scaleIntensity * 0.8);
  scaleColor *= (1.0 - scaleGroove * 0.7); // deep grooves
  // Groove interiors hint at core color (light leaking through)
  scaleColor += uCoreColor * scaleGroove * 0.15 * (0.3 + uGrowth * 0.5);
  // Scale plates catch light differently
  float scaleGlow = scaleIntensity * uGrowth * 0.5;
  scaleColor = mix(scaleColor, uCoreColor * 0.7 + surfaceColor * 0.3, scaleGlow);

  // ── Subsurface scattering — translucent shell look ──
  float sssEdge = pow(1.0 - NdV, 2.8);
  float sssBack = pow(max(dot(-V, keyDir), 0.0), 2.0);
  vec3 sssColor = uCoreColor * (sssEdge * 0.4 + sssBack * 0.25) * (0.5 + uGrowth * 0.5);

  // ── Specular — dual-lobe GGX (sharp + broad) ──
  float roughSharp = 0.2 - scaleHighlight * 0.08; // tight highlight
  float roughBroad = 0.55; // soft broad sheen

  vec3 H1 = normalize(keyDir + V);
  float NdH1 = max(dot(N, H1), 0.0);
  float specSharp = GGX(NdH1, roughSharp) * keyDiff;
  float specBroad = GGX(NdH1, roughBroad) * keyDiff;

  vec3 H2 = normalize(fillDir + V);
  float NdH2 = max(dot(N, H2), 0.0);
  float specFill = GGX(NdH2, roughSharp + 0.1) * fillDiff * 0.4;

  vec3 F0 = mix(vec3(0.04), uSpecColor * 0.3, 0.5); // dielectric-like base reflectance
  vec3 fresnel = fresnelSchlick(NdV, F0);
  vec3 specular = (specSharp * 0.7 + specBroad * 0.3 + specFill) * fresnel;
  specular += scaleHighlight * fresnel * 0.5;

  // ── Internal fire / burning core ──
  vec3 firePos = vLocalPos * 1.2 + vec3(0.0, -uTime * 0.2, 0.0);
  float fire1 = snoise(firePos + vec3(uSeed)) * 0.5 + 0.5;
  float fire2 = snoise(firePos * 1.5 + vec3(uSeed * 3.7) + uTime * 0.08) * 0.5 + 0.5;
  float fire3 = snoise(firePos * 0.7 + vec3(uSeed * 11.0) - uTime * 0.06) * 0.5 + 0.5;
  float fireTurbulence = pow(fire1 * 0.4 + fire2 * 0.35 + fire3 * 0.25, 1.5);

  float coreDepth = pow(NdV, 0.6);
  float centerFocus = smoothstep(0.0, 0.9, NdV);
  float fireShape = fireTurbulence * coreDepth * (0.3 + centerFocus * 0.7);

  float pulse = uBeat;
  float ember = 0.15 * fireShape;
  float blaze = pulse * (2.0 + uGrowth * 0.5) * fireShape * centerFocus;
  float fireIntensity = ember + blaze;

  // Beat pulses shift to deep blood-red, like a heart pumping
  vec3 heartRed = vec3(0.9, 0.08, 0.05);
  vec3 baseFireColor = uCoreColor + vec3(0.15, 0.05, -0.03) * fireTurbulence * 0.3;
  vec3 hotColor = mix(baseFireColor, heartRed, pulse * 0.7);
  vec3 fireColor = hotColor * fireIntensity;

  // ── Core glow — deep inner light ──
  float glow = pow(NdV, 2.0);
  float hotspot = pow(NdV, 14.0);
  float breath = sin(uTime * 0.3) * 0.5 + 0.5;
  float baseIntensity = 0.1 + breath * 0.05;
  float coreIntensity = baseIntensity + uGrowth * 0.6;
  vec3 core = mix(uCoreColor * 0.2, uCoreColor * 1.2, hotspot);

  // ── Fresnel rim — colored edge glow ──
  float fresnelRim = pow(1.0 - NdV, 4.0);
  vec3 rimColor = mix(surfaceColor * 0.5, uSpecColor * 0.5 + uCoreColor * 0.2, fresnelRim);
  vec3 rim = rimColor * fresnelRim;

  // ── Mist haze ──
  float mistNoise = snoise(vWorldPos * 1.5 + uTime * 0.06 + vec3(uSeed)) * 0.5 + 0.5;
  float mistAmount = 0.2 + uMistIntensity * 0.2;
  vec3 mist = uCoreColor * fresnelRim * mistAmount * (0.3 + mistNoise * 0.7);
  float genMist = max(0.0, uGrowth - 1.0) * 0.3;
  mist += uCoreColor * fresnelRim * genMist * mistNoise;

  // ── Environment reflection — makes it feel like a real object in space ──
  vec3 reflDir = reflect(-V, N);
  float envUp = reflDir.y * 0.5 + 0.5;
  float envSide = abs(reflDir.x) * 0.3;
  vec3 envColor = mix(
    vec3(0.06, 0.04, 0.03),
    vec3(0.35, 0.38, 0.42) + uSpecColor * 0.05,
    envUp
  );
  envColor += vec3(0.02) * envSide;
  vec3 envRefl = envColor * fresnel * 0.2 * (1.0 + scaleHighlight * 0.5);

  // ── Iridescence — subtle angle-dependent color shift ──
  float iridAngle = dot(N, V);
  vec3 iridColor = vec3(
    sin(iridAngle * 3.14 + 0.0) * 0.5 + 0.5,
    sin(iridAngle * 3.14 + 2.1) * 0.5 + 0.5,
    sin(iridAngle * 3.14 + 4.2) * 0.5 + 0.5
  );
  // Only apply iridescence subtly, more on rarer scale types
  float iridStrength = 0.03 + (uScaleType > 6.5 ? 0.12 : uScaleType > 5.5 ? 0.06 : 0.0);
  vec3 iridescence = iridColor * iridStrength * fresnelRim;

  // ── Compose ──
  vec3 color = ambient + diffuse;
  color = mix(color, scaleColor, max(scaleIntensity, scaleGroove) * 0.8);
  color += sssColor;
  color += rim;
  color += mist;
  color += core * glow * coreIntensity;
  color += fireColor;
  color += specular;
  color += envRefl;
  color += iridescence;

  // ACES-inspired tonemap for richer colors
  color = (color * (2.51 * color + 0.03)) / (color * (2.43 * color + 0.59) + 0.14);
  color = clamp(color, 0.0, 1.0);

  // Dissolve
  float dissolveNoise = snoise(vLocalPos * 5.0 + vec3(uSeed * 11.0));
  float dissolveThreshold = uDissolve * 2.0 - 1.0;
  if (dissolveNoise < dissolveThreshold) discard;

  float edgeDist = dissolveNoise - dissolveThreshold;
  if (edgeDist < 0.15 && uDissolve > 0.0) {
    color += uCoreColor * 2.5 * (1.0 - edgeDist / 0.15);
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

  float glow = exp(-d * 5.5) * 0.12;
  float breath = sin(uTime * 0.35) * 0.5 + 0.5;
  float intensity = (0.08 + breath * 0.04) + uGrowth * 0.25;

  vec3 color = uGlowColor * glow * intensity;
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
  float alpha = 0.4 * (1.0 - smoothstep(0.2, 1.0, d));
  alpha *= alpha; // softer falloff
  vec3 shadowColor = mix(vec3(0.03, 0.015, 0.025), vec3(0.0), d * 0.6);
  gl_FragColor = vec4(shadowColor, alpha);
}
`
