"use client";

/**
 * Client-side CLIP image embedding — matches what the backend backfill
 * computed with openai/clip-vit-base-patch32 via HuggingFace
 * transformers, so the 512-D vector we send to /scan/embedding-match
 * lives in the same cosine-similarity space as the catalog matrix
 * stored in R2.
 *
 * transformers.js loads the ONNX-exported version of the same model
 * (`Xenova/clip-vit-base-patch32`). Weights are ~150 MB, downloaded
 * once from HuggingFace CDN and cached by the browser afterwards.
 * CLIPVisionModelWithProjection runs the vision tower + projection
 * head, producing the same `image_embeds` output Python's
 * `CLIPModel.get_image_features()` returns.
 */

import {
  AutoProcessor,
  CLIPVisionModelWithProjection,
  RawImage,
} from "@huggingface/transformers";

const MODEL_ID = "Xenova/clip-vit-base-patch32";

let modelPromise: Promise<{
  model: Awaited<ReturnType<typeof CLIPVisionModelWithProjection.from_pretrained>>;
  processor: Awaited<ReturnType<typeof AutoProcessor.from_pretrained>>;
}> | null = null;

export type EmbedProgress = {
  status: "downloading" | "loading" | "ready";
  /** Fraction 0..1, only meaningful when status === "downloading". */
  progress: number;
  /** Total bytes for the current download shard, if reported. */
  totalMB: number;
};

/**
 * Kick off (or return the in-flight) model load. Idempotent — every
 * caller shares the same promise so we only fetch the ~150 MB
 * weights once per session.
 */
export function ensureEmbedModel(
  onProgress?: (p: EmbedProgress) => void,
): Promise<void> {
  if (!modelPromise) {
    modelPromise = (async () => {
      const progressCallback = onProgress
        ? (info: {
            status: string;
            file?: string;
            loaded?: number;
            total?: number;
          }) => {
            if (info.status === "progress" && info.total) {
              onProgress({
                status: "downloading",
                progress: (info.loaded ?? 0) / info.total,
                totalMB: info.total / (1024 * 1024),
              });
            } else if (info.status === "ready") {
              onProgress({ status: "ready", progress: 1, totalMB: 0 });
            }
          }
        : undefined;
      const [model, processor] = await Promise.all([
        CLIPVisionModelWithProjection.from_pretrained(MODEL_ID, {
          progress_callback: progressCallback,
        }),
        AutoProcessor.from_pretrained(MODEL_ID, {
          progress_callback: progressCallback,
        }),
      ]);
      onProgress?.({ status: "ready", progress: 1, totalMB: 0 });
      return { model, processor };
    })().catch((err) => {
      // Reset so a retry can trigger another attempt instead of
      // reusing a rejected promise forever.
      modelPromise = null;
      throw err;
    });
  }
  return modelPromise.then(() => undefined);
}

/**
 * Compute a 512-D CLIP image embedding from a canvas region.
 * `canvas` should already contain the cropped card frame; caller
 * decides the crop rectangle (matches the yellow bracket area).
 *
 * Returns a plain number array so it can be JSON-serialised into
 * the POST body directly.
 */
export async function computeEmbeddingFromCanvas(
  canvas: HTMLCanvasElement,
): Promise<number[]> {
  const ready = await modelPromise;
  if (!ready) {
    throw new Error("Model not initialised — call ensureEmbedModel() first");
  }
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) throw new Error("Canvas 2D context unavailable");
  const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
  // RawImage takes a Uint8ClampedArray + w/h + channel count. Canvas
  // ImageData is always RGBA (4 channels), which the processor knows
  // to handle.
  const rawImage = new RawImage(
    imgData.data,
    canvas.width,
    canvas.height,
    4,
  );
  const inputs = await ready.processor(rawImage);
  const output = await ready.model(inputs);
  const embeds = output.image_embeds;
  if (!embeds || !embeds.data) {
    throw new Error("Model output missing image_embeds");
  }
  return Array.from(embeds.data as Float32Array);
}

/** Convenience — has the model finished loading in this session? */
export function isEmbedModelReady(): boolean {
  return modelPromise != null;
}
