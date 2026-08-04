/**
 * Lazy-load stock Kokoro TTS in the browser (kokoro-js via jsDelivr).
 * Public Pages always uses stock Kokoro + Simlish IPA — never EA-derived
 * OpenVoice/Chatterbox/FT weights. Local Sims-timbre demos: v3/tts/SPEAK_STACK.md.
 */

import { simlishToKokoroInput } from "./simlish-ipa.js";

/** @type {any} */
let tts = null;
/** @type {Promise<any> | null} */
let loadPromise = null;
/** @type {HTMLAudioElement | null} */
let currentAudio = null;

const MODEL_ID = "onnx-community/Kokoro-82M-v1.0-ONNX";
const DEFAULT_VOICE = "af_heart";

/**
 * @param {(msg: string) => void} [onStatus]
 */
export async function ensureTts(onStatus) {
  if (tts) return tts;
  if (loadPromise) return loadPromise;
  loadPromise = (async () => {
    onStatus?.("Loading Kokoro TTS (first time ~90MB)…");
    const mod = await import("https://cdn.jsdelivr.net/npm/kokoro-js/+esm");
    const KokoroTTS = mod.KokoroTTS;
    const preferWebGpu = typeof navigator !== "undefined" && !!navigator.gpu;
    try {
      tts = await KokoroTTS.from_pretrained(MODEL_ID, {
        dtype: preferWebGpu ? "fp32" : "q8",
        device: preferWebGpu ? "webgpu" : "wasm",
      });
    } catch {
      tts = await KokoroTTS.from_pretrained(MODEL_ID, {
        dtype: "q8",
        device: "wasm",
      });
    }
    onStatus?.("Kokoro ready.");
    return tts;
  })();
  return loadPromise;
}

export function stopSpeaking() {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.src = "";
    currentAudio = null;
  }
}

/**
 * Speak Simlish orthography with stock Kokoro + custom IPA mapping.
 * @param {string} simlishText
 * @param {{ voice?: string, onStatus?: (msg: string) => void }} [opts]
 */
export async function speakSimlish(simlishText, opts = {}) {
  const text = (simlishText || "").trim();
  if (!text) return;
  stopSpeaking();
  const engine = await ensureTts(opts.onStatus);
  const prompt = simlishToKokoroInput(text);
  opts.onStatus?.("Synthesizing…");
  const audio = await engine.generate(prompt, {
    voice: opts.voice || DEFAULT_VOICE,
  });
  // kokoro-js RawAudio: toBlob / toWav / save depending on version
  let url;
  if (typeof audio.toBlob === "function") {
    url = URL.createObjectURL(await audio.toBlob());
  } else if (typeof audio.toWav === "function") {
    const wav = audio.toWav();
    url = URL.createObjectURL(new Blob([wav], { type: "audio/wav" }));
  } else if (audio.audio && audio.sampling_rate) {
    const wav = encodeWav(audio.audio, audio.sampling_rate);
    url = URL.createObjectURL(new Blob([wav], { type: "audio/wav" }));
  } else {
    throw new Error("Unsupported kokoro-js audio return shape");
  }
  const el = new Audio(url);
  currentAudio = el;
  el.onended = () => {
    URL.revokeObjectURL(url);
    if (currentAudio === el) currentAudio = null;
    opts.onStatus?.("Done.");
  };
  await el.play();
  opts.onStatus?.("Speaking…");
}

/**
 * @param {Float32Array|number[]} samples
 * @param {number} sampleRate
 */
function encodeWav(samples, sampleRate) {
  const numSamples = samples.length;
  const buffer = new ArrayBuffer(44 + numSamples * 2);
  const view = new DataView(buffer);
  const writeStr = (off, s) => {
    for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i));
  };
  writeStr(0, "RIFF");
  view.setUint32(4, 36 + numSamples * 2, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeStr(36, "data");
  view.setUint32(40, numSamples * 2, true);
  let offset = 44;
  for (let i = 0; i < numSamples; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    offset += 2;
  }
  return buffer;
}
