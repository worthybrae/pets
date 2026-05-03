/**
 * Voxel shape definitions for each pet species.
 * Each shape is an array of relative voxel positions forming a recognizable silhouette.
 * All voxels are white (255,255,255,255) by default.
 */

export interface ShapeVoxel {
  x: number;
  y: number;
  z: number;
  r: number;
  g: number;
  b: number;
  a: number;
}

export type Species =
  | "cat"
  | "dog"
  | "bunny"
  | "hamster"
  | "fox"
  | "owl"
  | "turtle"
  | "frog"
  | "wolf"
  | "deer"
  | "seahorse"
  | "hawk"
  | "dragon"
  | "phoenix"
  | "unicorn"
  | "leviathan"
  | "celestial";

export type Rarity = "common" | "uncommon" | "rare" | "legendary" | "mythic";

const W = 255; // white shorthand

function v(x: number, y: number, z: number): ShapeVoxel {
  return { x, y, z, r: W, g: W, b: W, a: W };
}

// === COMMON SPECIES (60%) ===

const cat: ShapeVoxel[] = [
  // Body (3 wide, 2 tall, 2 deep)
  v(0, 0, 0), v(1, 0, 0), v(2, 0, 0),
  v(0, 0, 1), v(1, 0, 1), v(2, 0, 1),
  v(0, 1, 0), v(1, 1, 0), v(2, 1, 0),
  v(0, 1, 1), v(1, 1, 1), v(2, 1, 1),
  // Head (2x2x2 on top front)
  v(0, 2, 0), v(1, 2, 0),
  v(0, 2, 1), v(1, 2, 1),
  v(0, 3, 0), v(1, 3, 0),
  v(0, 3, 1), v(1, 3, 1),
  // Ears (2 voxels on top corners of head)
  v(0, 4, 0), v(1, 4, 0),
  // Tail (3 voxels extending back and up)
  v(2, 1, 2), v(2, 2, 2), v(2, 3, 2),
];

const dog: ShapeVoxel[] = [
  // Body (3 wide, 2 tall, 3 deep - longer than cat)
  v(0, 0, 0), v(1, 0, 0), v(2, 0, 0),
  v(0, 0, 1), v(1, 0, 1), v(2, 0, 1),
  v(0, 0, 2), v(1, 0, 2), v(2, 0, 2),
  v(0, 1, 0), v(1, 1, 0), v(2, 1, 0),
  v(0, 1, 1), v(1, 1, 1), v(2, 1, 1),
  v(0, 1, 2), v(1, 1, 2), v(2, 1, 2),
  // Head (2x2x2 front)
  v(0, 2, 0), v(1, 2, 0),
  v(0, 2, 1), v(1, 2, 1),
  v(0, 3, 0), v(1, 3, 0),
  // Floppy ears (hang down from sides of head)
  v(-1, 2, 0), v(2, 2, 0),
  // Tail (wagging up)
  v(2, 2, 2), v(2, 3, 2),
];

const bunny: ShapeVoxel[] = [
  // Body (2 wide, 2 tall, 2 deep - compact)
  v(0, 0, 0), v(1, 0, 0),
  v(0, 0, 1), v(1, 0, 1),
  v(0, 1, 0), v(1, 1, 0),
  v(0, 1, 1), v(1, 1, 1),
  // Head (2x2x1)
  v(0, 2, 0), v(1, 2, 0),
  v(0, 3, 0), v(1, 3, 0),
  // Long ears (3 voxels tall!)
  v(0, 4, 0), v(0, 5, 0), v(0, 6, 0),
  v(1, 4, 0), v(1, 5, 0), v(1, 6, 0),
  // Fluffy tail (round puff)
  v(0, 1, 2), v(1, 1, 2),
];

const hamster: ShapeVoxel[] = [
  // Chubby round body (3x2x2)
  v(0, 0, 0), v(1, 0, 0), v(2, 0, 0),
  v(0, 0, 1), v(1, 0, 1), v(2, 0, 1),
  v(0, 1, 0), v(1, 1, 0), v(2, 1, 0),
  v(0, 1, 1), v(1, 1, 1), v(2, 1, 1),
  // Extra chub on sides
  v(-1, 0, 0), v(3, 0, 0),
  // Head (sits on top, 2x1x2)
  v(0, 2, 0), v(1, 2, 0),
  v(0, 2, 1), v(1, 2, 1),
  // Tiny ears
  v(0, 3, 0), v(1, 3, 0),
  // Tiny paws in front
  v(0, 0, -1), v(1, 0, -1),
];

// === UNCOMMON SPECIES (25%) ===

const fox: ShapeVoxel[] = [
  // Sleek body (3 wide, 2 tall, 2 deep)
  v(0, 0, 0), v(1, 0, 0), v(2, 0, 0),
  v(0, 0, 1), v(1, 0, 1), v(2, 0, 1),
  v(0, 1, 0), v(1, 1, 0), v(2, 1, 0),
  v(0, 1, 1), v(1, 1, 1), v(2, 1, 1),
  // Pointed head (triangular profile)
  v(0, 2, 0), v(1, 2, 0),
  v(0, 3, 0),
  // Pointed ears
  v(-1, 3, 0), v(1, 3, 0),
  v(-1, 4, 0), v(1, 4, 0),
  // Big bushy tail (4 voxels)
  v(2, 0, 2), v(2, 1, 2), v(2, 1, 3), v(2, 2, 3),
];

const owl: ShapeVoxel[] = [
  // Round body (2x3x2)
  v(0, 0, 0), v(1, 0, 0),
  v(0, 0, 1), v(1, 0, 1),
  v(0, 1, 0), v(1, 1, 0),
  v(0, 1, 1), v(1, 1, 1),
  v(0, 2, 0), v(1, 2, 0),
  v(0, 2, 1), v(1, 2, 1),
  // Wide head (wider than body)
  v(-1, 3, 0), v(0, 3, 0), v(1, 3, 0), v(2, 3, 0),
  v(0, 4, 0), v(1, 4, 0),
  // Ear tufts
  v(-1, 4, 0), v(2, 4, 0),
  v(-1, 5, 0), v(2, 5, 0),
  // Wings (spread out)
  v(-1, 1, 0), v(2, 1, 0),
  v(-1, 2, 0), v(2, 2, 0),
];

const turtle: ShapeVoxel[] = [
  // Shell (dome shape: 3x2x3)
  v(0, 1, 0), v(1, 1, 0), v(2, 1, 0),
  v(0, 1, 1), v(1, 1, 1), v(2, 1, 1),
  v(0, 1, 2), v(1, 1, 2), v(2, 1, 2),
  // Shell top
  v(1, 2, 0), v(1, 2, 1), v(1, 2, 2),
  v(0, 2, 1), v(2, 2, 1),
  // Head poking out front
  v(1, 1, -1), v(1, 2, -1),
  // Legs (4 stubby legs)
  v(0, 0, 0), v(2, 0, 0),
  v(0, 0, 2), v(2, 0, 2),
  // Tail
  v(1, 0, 3),
];

const frog: ShapeVoxel[] = [
  // Flat wide body (3x1x2)
  v(0, 0, 0), v(1, 0, 0), v(2, 0, 0),
  v(0, 0, 1), v(1, 0, 1), v(2, 0, 1),
  // Slightly taller front
  v(0, 1, 0), v(1, 1, 0), v(2, 1, 0),
  // Big eyes (bulging up)
  v(0, 2, 0), v(2, 2, 0),
  // Front legs (splayed)
  v(-1, 0, -1), v(3, 0, -1),
  // Back legs (powerful, bent)
  v(-1, 0, 2), v(3, 0, 2),
  v(-1, 0, 3), v(3, 0, 3),
  // Belly
  v(1, 0, -1),
];

// === RARE SPECIES (10%) ===

const wolf: ShapeVoxel[] = [
  // Muscular body (4 wide, 3 tall, 2 deep)
  v(0, 0, 0), v(1, 0, 0), v(2, 0, 0), v(3, 0, 0),
  v(0, 0, 1), v(1, 0, 1), v(2, 0, 1), v(3, 0, 1),
  v(0, 1, 0), v(1, 1, 0), v(2, 1, 0), v(3, 1, 0),
  v(0, 1, 1), v(1, 1, 1), v(2, 1, 1), v(3, 1, 1),
  v(1, 2, 0), v(2, 2, 0),
  // Head (angular)
  v(0, 2, 0), v(0, 3, 0),
  v(-1, 2, 0), v(-1, 3, 0),
  // Pointed ears
  v(-1, 4, 0), v(0, 4, 0),
  // Tail (bushy, swept)
  v(3, 1, 2), v(3, 2, 2), v(3, 2, 3),
];

const deer: ShapeVoxel[] = [
  // Elegant body (3 wide, 2 tall, 2 deep)
  v(0, 0, 0), v(1, 0, 0), v(2, 0, 0),
  v(0, 0, 1), v(1, 0, 1), v(2, 0, 1),
  v(0, 1, 0), v(1, 1, 0), v(2, 1, 0),
  v(0, 1, 1), v(1, 1, 1), v(2, 1, 1),
  // Long neck
  v(0, 2, 0), v(0, 3, 0),
  // Head
  v(0, 4, 0), v(-1, 4, 0),
  // Antlers (branching)
  v(0, 5, 0), v(-1, 5, 0),
  v(0, 6, 0), v(-1, 6, 0),
  v(1, 6, 0), v(-2, 6, 0),
  // Legs (tall, thin)
  v(0, -1, 0), v(2, -1, 0),
  v(0, -1, 1), v(2, -1, 1),
];

const seahorse: ShapeVoxel[] = [
  // Curled tail (bottom)
  v(2, 0, 0), v(1, 0, 0), v(0, 0, 0),
  v(0, 1, 0),
  // Body (vertical, s-curve)
  v(0, 2, 0), v(1, 2, 0),
  v(1, 3, 0), v(2, 3, 0),
  v(2, 4, 0), v(1, 4, 0),
  v(1, 5, 0), v(0, 5, 0),
  // Head
  v(0, 6, 0), v(0, 7, 0),
  v(-1, 7, 0),
  // Crown/fin on top
  v(0, 8, 0), v(1, 8, 0),
  // Side fin
  v(2, 4, 1), v(2, 5, 1),
];

const hawk: ShapeVoxel[] = [
  // Streamlined body (2x2x3)
  v(0, 0, 0), v(1, 0, 0),
  v(0, 0, 1), v(1, 0, 1),
  v(0, 0, 2), v(1, 0, 2),
  v(0, 1, 0), v(1, 1, 0),
  v(0, 1, 1), v(1, 1, 1),
  // Head (sharp)
  v(0, 2, 0), v(1, 2, 0),
  v(0, 3, 0),
  // Wings (wide spread)
  v(-1, 1, 1), v(-2, 1, 1), v(-3, 1, 1),
  v(2, 1, 1), v(3, 1, 1), v(4, 1, 1),
  // Tail feathers
  v(0, 0, 3), v(1, 0, 3),
];

// === LEGENDARY SPECIES (4%) ===

const dragon: ShapeVoxel[] = [
  // Powerful body (4x3x3)
  v(0, 0, 0), v(1, 0, 0), v(2, 0, 0), v(3, 0, 0),
  v(0, 0, 1), v(1, 0, 1), v(2, 0, 1), v(3, 0, 1),
  v(0, 0, 2), v(1, 0, 2), v(2, 0, 2), v(3, 0, 2),
  v(1, 1, 0), v(2, 1, 0), v(3, 1, 0),
  v(1, 1, 1), v(2, 1, 1), v(3, 1, 1),
  // Head (angular, with horns)
  v(0, 1, 0), v(0, 2, 0), v(-1, 2, 0),
  v(0, 3, 0), v(-1, 3, 0),
  // Horns
  v(-1, 4, 0), v(0, 4, 0),
  // Wings (large, spread)
  v(1, 2, -1), v(2, 2, -1), v(3, 2, -1), v(4, 2, -1),
  v(1, 2, 3), v(2, 2, 3), v(3, 2, 3), v(4, 2, 3),
  // Tail (long, with spike)
  v(3, 0, 3), v(3, 0, 4), v(3, 1, 4), v(3, 1, 5),
];

const phoenix: ShapeVoxel[] = [
  // Elegant body (2x3x2)
  v(0, 0, 0), v(1, 0, 0),
  v(0, 0, 1), v(1, 0, 1),
  v(0, 1, 0), v(1, 1, 0),
  v(0, 1, 1), v(1, 1, 1),
  v(0, 2, 0), v(1, 2, 0),
  // Head with crest
  v(0, 3, 0), v(1, 3, 0),
  v(0, 4, 0),
  v(-1, 4, 0), v(1, 4, 0),
  // Wings (spread wide, sweeping)
  v(-1, 2, 0), v(-2, 2, 0), v(-3, 2, 1),
  v(2, 2, 0), v(3, 2, 0), v(4, 2, 1),
  v(-2, 1, 0), v(3, 1, 0),
  // Long tail feathers (flowing)
  v(0, 0, 2), v(1, 0, 2),
  v(0, -1, 3), v(1, -1, 3),
  v(0, -1, 4), v(1, -1, 4), v(0, -2, 5),
];

const unicorn: ShapeVoxel[] = [
  // Graceful body (3x2x2)
  v(0, 0, 0), v(1, 0, 0), v(2, 0, 0),
  v(0, 0, 1), v(1, 0, 1), v(2, 0, 1),
  v(0, 1, 0), v(1, 1, 0), v(2, 1, 0),
  v(0, 1, 1), v(1, 1, 1), v(2, 1, 1),
  // Neck (tall, arched)
  v(0, 2, 0), v(0, 3, 0),
  // Head
  v(0, 4, 0), v(-1, 4, 0),
  v(0, 4, 1),
  // Horn (3 voxels, spiraling up)
  v(0, 5, 0), v(0, 6, 0), v(0, 7, 0),
  // Mane (flowing down neck)
  v(0, 3, 1), v(0, 2, 1),
  // Legs
  v(0, -1, 0), v(2, -1, 0),
  v(0, -1, 1), v(2, -1, 1),
  // Tail (flowing)
  v(2, 1, 2), v(2, 0, 2), v(2, 0, 3),
];

// === MYTHIC SPECIES (1%) ===

const leviathan: ShapeVoxel[] = [
  // Massive serpentine body (undulating)
  v(0, 0, 0), v(1, 0, 0), v(2, 0, 0),
  v(2, 1, 0), v(3, 1, 0), v(4, 1, 0),
  v(4, 0, 0), v(5, 0, 0), v(6, 0, 0),
  v(6, 1, 0), v(7, 1, 0),
  // Body depth
  v(0, 0, 1), v(1, 0, 1), v(2, 0, 1),
  v(2, 1, 1), v(3, 1, 1), v(4, 1, 1),
  v(4, 0, 1), v(5, 0, 1), v(6, 0, 1),
  // Head (massive, angular)
  v(-1, 0, 0), v(-1, 1, 0), v(-2, 1, 0),
  v(-1, 0, 1), v(-1, 1, 1),
  v(-2, 2, 0), v(-1, 2, 0),
  // Fins along body
  v(1, 1, -1), v(3, 2, -1), v(5, 1, -1),
  // Tail (massive)
  v(7, 2, 0), v(7, 2, 1), v(8, 3, 0),
];

const celestial: ShapeVoxel[] = [
  // Core (glowing orb shape, 3x3x3 hollow)
  v(0, 1, 0), v(1, 1, 0), v(2, 1, 0),
  v(0, 1, 2), v(1, 1, 2), v(2, 1, 2),
  v(0, 1, 1), v(2, 1, 1),
  v(0, 0, 0), v(1, 0, 0), v(2, 0, 0),
  v(0, 0, 1), v(2, 0, 1),
  v(0, 0, 2), v(1, 0, 2), v(2, 0, 2),
  v(0, 2, 0), v(1, 2, 0), v(2, 2, 0),
  v(0, 2, 1), v(2, 2, 1),
  v(0, 2, 2), v(1, 2, 2), v(2, 2, 2),
  // Radiating points (star shape)
  v(1, 4, 1),  // top
  v(1, -2, 1), // bottom
  v(-2, 1, 1), // left
  v(4, 1, 1),  // right
  v(1, 1, -2), // front
  v(1, 1, 4),  // back
  // Connecting rays
  v(1, 3, 1), v(1, -1, 1),
  v(-1, 1, 1), v(3, 1, 1),
  v(1, 1, -1), v(1, 1, 3),
];

// Export the shape map
export const petShapes: Record<Species, ShapeVoxel[]> = {
  cat,
  dog,
  bunny,
  hamster,
  fox,
  owl,
  turtle,
  frog,
  wolf,
  deer,
  seahorse,
  hawk,
  dragon,
  phoenix,
  unicorn,
  leviathan,
  celestial,
};

// Species by rarity for reference
export const speciesByRarity: Record<Rarity, Species[]> = {
  common: ["cat", "dog", "bunny", "hamster"],
  uncommon: ["fox", "owl", "turtle", "frog"],
  rare: ["wolf", "deer", "seahorse", "hawk"],
  legendary: ["dragon", "phoenix", "unicorn"],
  mythic: ["leviathan", "celestial"],
};

// Rarity colors for UI
export const rarityColors: Record<Rarity, string> = {
  common: "#9ca3af",     // gray
  uncommon: "#22c55e",   // green
  rare: "#3b82f6",       // blue
  legendary: "#a855f7",  // purple
  mythic: "#ec4899",     // pink (will be animated rainbow)
};
