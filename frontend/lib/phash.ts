/**
 * Client-side perceptual hash (pHash) matching what Python's
 * ImageHash.phash() produces on the backend, so a hash computed here
 * lines up with the hashes seeded into cards.image_phash.
 *
 * Algorithm (identical to imagehash.phash with default hash_size=8,
 * highfreq_factor=4):
 *   1. Resize + grayscale to 32×32
 *   2. Apply 2-D DCT-II (naive O(N⁴) — 1M ops at N=32, ~10-30ms in V8)
 *   3. Take top-left 8×8 low-frequency block (64 values)
 *   4. Median of those 64 → threshold
 *   5. Bits: value > median → 1, else 0 (row-major)
 *   6. 64 bits → 16-char hex, big-endian
 *
 * Scaling factors from the DCT don't matter — the median comparison is
 * invariant under uniform scaling, so we skip normalization to keep the
 * inner loop tight.
 */

const HASH_SIZE = 8;
const IMG_SIZE = 32;

// Precomputed DCT-II cosine table: cos[n * IMG_SIZE + k] = cos((2n+1) * kπ / (2N))
// One-time cost at module load, reused for every hash.
const cosTable = (() => {
  const table = new Float32Array(IMG_SIZE * IMG_SIZE);
  for (let n = 0; n < IMG_SIZE; n++) {
    for (let k = 0; k < IMG_SIZE; k++) {
      table[n * IMG_SIZE + k] = Math.cos(((2 * n + 1) * k * Math.PI) / (2 * IMG_SIZE));
    }
  }
  return table;
})();

// Scratch buffers reused across calls to avoid GC churn during the
// bulk-scan capture loop (fires every 300-500ms).
const grayscale = new Float32Array(IMG_SIZE * IMG_SIZE);
const dctRow = new Float32Array(IMG_SIZE * IMG_SIZE);
const dctFull = new Float32Array(IMG_SIZE * IMG_SIZE);

/**
 * Compute the 16-char hex pHash of a video frame. Caller draws the
 * frame onto a hidden 32×32 canvas at the target crop, then passes the
 * ImageData in.
 *
 * Returns null on empty/degenerate input (all-zero variance) so the
 * capture loop can skip the search entirely.
 */
export function computePhash(imageData: ImageData): string | null {
  const { data, width, height } = imageData;
  if (width !== IMG_SIZE || height !== IMG_SIZE) {
    throw new Error(
      `computePhash expects ${IMG_SIZE}x${IMG_SIZE} ImageData, got ${width}x${height}`,
    );
  }

  // ── Step 1: RGB → luma. PIL's Image.convert("L") uses ITU-R BT.601
  // coefficients (0.299 / 0.587 / 0.114), and the backend hashes go
  // through PIL. Match those exact weights or we'll drift by a few
  // bits vs the server-computed catalog hashes. Alpha ignored.
  for (let i = 0, p = 0; i < data.length; i += 4, p++) {
    grayscale[p] = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
  }

  // Quick degeneracy check — pure-black frames (camera not ready yet)
  // produce a garbage all-zero hash that matches nothing.
  let sum = 0;
  for (let i = 0; i < grayscale.length; i++) sum += grayscale[i];
  if (sum < 1) return null;

  // ── Step 2a: 1-D DCT along rows.
  for (let y = 0; y < IMG_SIZE; y++) {
    for (let k = 0; k < IMG_SIZE; k++) {
      let s = 0;
      for (let n = 0; n < IMG_SIZE; n++) {
        s += grayscale[y * IMG_SIZE + n] * cosTable[n * IMG_SIZE + k];
      }
      dctRow[y * IMG_SIZE + k] = s;
    }
  }

  // ── Step 2b: 1-D DCT along columns (of the row-DCT'd matrix).
  for (let x = 0; x < IMG_SIZE; x++) {
    for (let k = 0; k < IMG_SIZE; k++) {
      let s = 0;
      for (let n = 0; n < IMG_SIZE; n++) {
        s += dctRow[n * IMG_SIZE + x] * cosTable[n * IMG_SIZE + k];
      }
      dctFull[k * IMG_SIZE + x] = s;
    }
  }

  // ── Step 3: Low-frequency 8×8 block (top-left of DCT output).
  const lowFreq = new Float32Array(HASH_SIZE * HASH_SIZE);
  for (let u = 0; u < HASH_SIZE; u++) {
    for (let v = 0; v < HASH_SIZE; v++) {
      lowFreq[u * HASH_SIZE + v] = dctFull[u * IMG_SIZE + v];
    }
  }

  // ── Step 4: Median of the 64 low-freq values.
  const sorted = Array.from(lowFreq).sort((a, b) => a - b);
  const median = (sorted[31] + sorted[32]) / 2;

  // ── Step 5+6: Threshold → 64 bits, packed row-major into 16 hex chars.
  let hex = "";
  for (let byte = 0; byte < 16; byte++) {
    let nibble = 0;
    for (let bit = 0; bit < 4; bit++) {
      const idx = byte * 4 + bit;
      if (lowFreq[idx] > median) nibble |= 1 << (3 - bit);
    }
    hex += nibble.toString(16);
  }
  return hex;
}

/**
 * Hamming distance between two 16-char hex pHashes. Result range: 0-64.
 *
 * We can't use BigInt XOR + popcount because BigInt allocation would
 * dominate at 42 k comparisons per frame. Two 32-bit halves + a
 * table-free popcount (Kernighan's trick) is the fast path.
 */
export function hammingDistance(a: string, b: string): number {
  if (a.length !== 16 || b.length !== 16) return 64;
  // Split into two 8-hex halves (32 bits each) — parseInt caps at 32 bits.
  const aHi = parseInt(a.slice(0, 8), 16) | 0;
  const aLo = parseInt(a.slice(8, 16), 16) | 0;
  const bHi = parseInt(b.slice(0, 8), 16) | 0;
  const bLo = parseInt(b.slice(8, 16), 16) | 0;
  return popcount32(aHi ^ bHi) + popcount32(aLo ^ bLo);
}

function popcount32(n: number): number {
  n = n - ((n >>> 1) & 0x55555555);
  n = (n & 0x33333333) + ((n >>> 2) & 0x33333333);
  n = (n + (n >>> 4)) & 0x0f0f0f0f;
  // Must use Math.imul — the naive `n * 0x01010101` overflows JS's
  // double-precision int range for values above 24 bits and returns
  // wrong bit counts. Math.imul does true 32-bit multiplication.
  return (Math.imul(n, 0x01010101) >>> 24) & 0x7f;
}

/**
 * Nearest-neighbor search across the pHash catalog. Returns the closest
 * card_id along with its distance; caller decides whether the distance
 * is small enough to trust (typically ≤ 15 for camera-vs-render match).
 *
 * Linear O(N) — 42 k comparisons × ~30 ns/compare = ~1-2 ms. Way inside
 * the 300-500 ms capture cadence.
 */
export type PhashCatalog = {
  count: number;
  generated_at: string;
  ids: string[];
  hashes: string[];
};

export type PhashMatch = {
  cardId: string;
  distance: number;
};

export function findNearest(
  targetHash: string,
  catalog: PhashCatalog,
): PhashMatch | null {
  if (!catalog.ids.length) return null;
  let bestDistance = 65;
  let bestId = "";
  const { ids, hashes } = catalog;
  const targetHi = parseInt(targetHash.slice(0, 8), 16) | 0;
  const targetLo = parseInt(targetHash.slice(8, 16), 16) | 0;
  for (let i = 0; i < hashes.length; i++) {
    const h = hashes[i];
    const hHi = parseInt(h.slice(0, 8), 16) | 0;
    const hLo = parseInt(h.slice(8, 16), 16) | 0;
    const d = popcount32(targetHi ^ hHi) + popcount32(targetLo ^ hLo);
    if (d < bestDistance) {
      bestDistance = d;
      bestId = ids[i];
      if (d === 0) break;
    }
  }
  if (!bestId) return null;
  return { cardId: bestId, distance: bestDistance };
}

// Pokemon card aspect ratio (245 × 342 = ~0.716). Every catalog image
// is stored at this aspect, so we crop the camera frame to match
// before hashing — otherwise the 32×32 resize warps the two inputs
// differently (a 16:9 video frame squishes horizontally while a 3:4
// card image stays roughly square) and no hash bits will line up.
const CARD_ASPECT = 245 / 342;

// Shrink the auto-crop this much from each edge (fraction of the
// crop rectangle). Matches the visual "align card here" corner
// brackets in the viewfinder — user is aiming to fill the brackets,
// not the whole viewport, so hashing a little inside the crop drops
// most of the yellow-border rim + background.
const CARD_CROP_INSET = 0.06;

/**
 * Compute the largest card-aspect (3:4-ish) centered rectangle that
 * fits in a video of the given source dimensions, then shrink it by
 * CARD_CROP_INSET on each side. Result is what we tell drawImage to
 * sample from — so background / hand / rounded viewport corners are
 * left out of the hash.
 */
export function computeCardCrop(
  videoWidth: number,
  videoHeight: number,
): { x: number; y: number; w: number; h: number } {
  const videoAspect = videoWidth / videoHeight;
  let w: number;
  let h: number;
  if (videoAspect > CARD_ASPECT) {
    // Video is wider than a card — height is the limiting side.
    h = videoHeight;
    w = h * CARD_ASPECT;
  } else {
    // Video is taller/narrower than a card — width limits.
    w = videoWidth;
    h = w / CARD_ASPECT;
  }
  const shrink = 1 - CARD_CROP_INSET * 2;
  w *= shrink;
  h *= shrink;
  return {
    x: (videoWidth - w) / 2,
    y: (videoHeight - h) / 2,
    w,
    h,
  };
}

/**
 * Extract a 32×32 ImageData from a video element, cropping to the
 * card region first so the hash reflects the card art rather than the
 * whole 16:9 sensor. Passing an explicit crop bypasses the automatic
 * card-aspect calculation — useful for debugging.
 *
 * imageSmoothingQuality is forced to "high" so the extreme downscale
 * (a ~1280 × 1920 crop → 32 × 32) doesn't produce a garbled DCT input.
 * Default canvas smoothing is bilinear-low; the "high" tier gives
 * something closer to a Lanczos-style filter, matching what PIL uses
 * to seed the catalog hashes.
 */
export function extractFrameForHash(
  video: HTMLVideoElement,
  canvas: HTMLCanvasElement,
  crop?: { x: number; y: number; w: number; h: number } | null,
): ImageData | null {
  if (video.readyState < 2 || !video.videoWidth || !video.videoHeight) {
    return null;
  }
  canvas.width = IMG_SIZE;
  canvas.height = IMG_SIZE;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) return null;
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  const c = crop ?? computeCardCrop(video.videoWidth, video.videoHeight);
  ctx.drawImage(video, c.x, c.y, c.w, c.h, 0, 0, IMG_SIZE, IMG_SIZE);
  return ctx.getImageData(0, 0, IMG_SIZE, IMG_SIZE);
}
