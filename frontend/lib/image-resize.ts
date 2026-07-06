/**
 * Client-side image resize for uploads.
 *
 * Reads a File, draws it into a canvas at ≤ maxLongEdge px, exports as
 * JPEG with adjustable quality until the result fits under the target
 * byte budget. Returns a `data:image/jpeg;base64,...` string.
 *
 * Used for master-set cover uploads so we don't ship 5MB phone photos
 * to the backend / store them in the DB.
 */

export type ResizeOptions = {
  /** Max dimension of the longer edge, in pixels. Defaults to 1200. */
  maxLongEdge?: number;
  /** Target ceiling for the resulting data URL string length. Defaults
   *  to 700_000 (~500KB of image after base64 overhead). */
  maxBytes?: number;
  /** Starting JPEG quality [0..1]. Steps down by 0.1 until the byte
   *  budget is met, floor 0.5. Defaults to 0.85. */
  startQuality?: number;
};

const DEFAULTS = {
  maxLongEdge: 1200,
  maxBytes: 700_000,
  startQuality: 0.85,
};

export async function fileToResizedDataUrl(
  file: File,
  opts: ResizeOptions = {},
): Promise<string> {
  const { maxLongEdge, maxBytes, startQuality } = { ...DEFAULTS, ...opts };
  if (!file.type.startsWith("image/")) {
    throw new Error("File must be an image");
  }

  const bitmap = await loadImage(file);
  const scale = Math.min(1, maxLongEdge / Math.max(bitmap.width, bitmap.height));
  const targetW = Math.round(bitmap.width * scale);
  const targetH = Math.round(bitmap.height * scale);

  const canvas = document.createElement("canvas");
  canvas.width = targetW;
  canvas.height = targetH;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas 2D unavailable");
  ctx.drawImage(bitmap, 0, 0, targetW, targetH);

  // Step quality down until we fit, or bottom out at 0.5.
  let quality = startQuality;
  let dataUrl = canvas.toDataURL("image/jpeg", quality);
  while (dataUrl.length > maxBytes && quality > 0.5) {
    quality = Math.max(0.5, quality - 0.1);
    dataUrl = canvas.toDataURL("image/jpeg", quality);
  }
  if (dataUrl.length > maxBytes) {
    // Last resort — shrink the canvas 25% and retry once.
    canvas.width = Math.round(targetW * 0.75);
    canvas.height = Math.round(targetH * 0.75);
    const ctx2 = canvas.getContext("2d");
    if (!ctx2) throw new Error("Canvas 2D unavailable");
    ctx2.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    dataUrl = canvas.toDataURL("image/jpeg", 0.7);
  }
  return dataUrl;
}

function loadImage(file: File): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve(img);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Failed to decode image"));
    };
    img.src = url;
  });
}
