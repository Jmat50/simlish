/**
 * Lazy-load stock Kokoro TTS in the browser (kokoro-js via jsDelivr).
 * Public Pages always uses stock Kokoro + Simlish IPA — never EA-derived weights.
 *
 * Performance: default q8 (~92MB) on WASM/WebGPU; stream clause chunks for TTFA;
 * punchier delivery via speed≈1.12. Weights stay on Hugging Face Hub CDN
 * (do not commit ONNX into docs/; mirror to R2/own HF repo only if Hub 429s).
 */

import { simlishToKokoroInput } from "./simlish-ipa.js?v=20260806b";

/** @type {any} */
let tts = null;
/** @type {Promise<any> | null} */
let loadPromise = null;
/** @type {any} */
let kokoroMod = null;
/** @type {number} */
let speakGeneration = 0;
/** @type {AudioContext | null} */
let audioCtx = null;
/** @type {AudioBufferSourceNode[]} */
let activeSources = [];

const MODEL_ID = "onnx-community/Kokoro-82M-v1.0-ONNX";
const KOKORO_JS = "https://cdn.jsdelivr.net/npm/kokoro-js@1.2.1/+esm";
const DEFAULT_VOICE = "af_heart";
/** Punchier than narration default; Kokoro accepts ~0.5–2.0. */
const DEFAULT_SPEED = 1.12;

/**
 * Prefer small q8 weights (~92MB). Try WebGPU+q8 first for synth speed;
 * fall back if ORT rejects (see hexgrad/kokoro#68). Never silently download fp32 (~326MB).
 * @type {{ device: string, dtype: string, label: string }[]}
 */
const LOAD_ATTEMPTS = [
  { device: "webgpu", dtype: "q8", label: "WebGPU q8 (~92MB)" },
  { device: "webgpu", dtype: "fp16", label: "WebGPU fp16 (~163MB)" },
  { device: "wasm", dtype: "q8", label: "WASM q8 (~92MB)" },
];

/**
 * @param {(msg: string) => void} [onStatus]
 * @param {{ file?: string, progress?: number, status?: string, loaded?: number, total?: number }} [data]
 */
function reportLoadProgress(onStatus, data) {
  if (!onStatus || !data) return;
  if (typeof data.progress === "number" && data.progress >= 0 && data.progress <= 1) {
    onStatus(`Loading Kokoro TTS… ${Math.round(data.progress * 100)}%`);
    return;
  }
  if (typeof data.loaded === "number" && typeof data.total === "number" && data.total > 0) {
    onStatus(`Loading Kokoro TTS… ${Math.round((data.loaded / data.total) * 100)}%`);
  }
}

async function loadKokoroMod() {
  if (kokoroMod) return kokoroMod;
  kokoroMod = await import(KOKORO_JS);
  return kokoroMod;
}

/**
 * @param {(msg: string) => void} [onStatus]
 */
export async function ensureTts(onStatus) {
  if (tts) return tts;
  if (loadPromise) return loadPromise;
  loadPromise = (async () => {
    onStatus?.("Loading Kokoro TTS (~92MB first time)…");
    const mod = await loadKokoroMod();
    const KokoroTTS = mod.KokoroTTS;
    const hasGpu = typeof navigator !== "undefined" && !!navigator.gpu;
    const attempts = hasGpu
      ? LOAD_ATTEMPTS
      : LOAD_ATTEMPTS.filter((a) => a.device === "wasm");

    let lastErr = /** @type {unknown} */ (null);
    for (const attempt of attempts) {
      try {
        onStatus?.(`Loading Kokoro (${attempt.label})…`);
        tts = await KokoroTTS.from_pretrained(MODEL_ID, {
          dtype: attempt.dtype,
          device: attempt.device,
          progress_callback: (data) => reportLoadProgress(onStatus, data),
        });
        onStatus?.(`Kokoro ready (${attempt.label}).`);
        return tts;
      } catch (err) {
        lastErr = err;
        console.warn(`Kokoro load failed (${attempt.label}):`, err);
        tts = null;
      }
    }
    loadPromise = null;
    throw lastErr instanceof Error
      ? lastErr
      : new Error("Failed to load Kokoro TTS");
  })();
  return loadPromise;
}

function getAudioContext() {
  if (!audioCtx) {
    const W = /** @type {Window & { webkitAudioContext?: typeof AudioContext }} */ (window);
    const AC = W.AudioContext || W.webkitAudioContext;
    if (!AC) throw new Error("Web Audio API not available");
    audioCtx = new AC();
  }
  return audioCtx;
}

function stopActiveSources() {
  for (const src of activeSources) {
    try {
      src.stop();
    } catch {
      /* already stopped */
    }
    try {
      src.disconnect();
    } catch {
      /* ignore */
    }
  }
  activeSources = [];
}

/**
 * Cancel in-flight synthesis and stop playback.
 */
export function stopSpeaking() {
  speakGeneration += 1;
  stopActiveSources();
}

/**
 * Split convert output into rhythm units (lines / clauses) for streaming TTFA.
 * @param {string} text
 * @returns {string[]}
 */
export function splitSpeakChunks(text) {
  const raw = (text || "").replace(/\r\n/g, "\n").trim();
  if (!raw) return [];
  /** @type {string[]} */
  const chunks = [];
  for (const line of raw.split(/\n+/)) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const parts = trimmed.match(/[^.!?…]+[.!?…]+|[^.!?…]+$/g);
    if (!parts) {
      chunks.push(trimmed);
      continue;
    }
    for (const p of parts) {
      const c = p.trim();
      if (c) chunks.push(c);
    }
  }
  return chunks.length ? chunks : [raw];
}

/**
 * @param {any} rawAudio kokoro-js RawAudio
 * @returns {{ samples: Float32Array, sampleRate: number }}
 */
function rawAudioToSamples(rawAudio) {
  if (rawAudio?.audio && rawAudio.sampling_rate) {
    const audio = rawAudio.audio;
    const samples =
      audio instanceof Float32Array ? audio : Float32Array.from(audio);
    return { samples, sampleRate: rawAudio.sampling_rate };
  }
  throw new Error("Unsupported kokoro-js audio return shape");
}

/**
 * @param {AudioContext} ctx
 * @param {Float32Array} samples
 * @param {number} sampleRate
 * @returns {AudioBuffer}
 */
function samplesToBuffer(ctx, samples, sampleRate) {
  const buffer = ctx.createBuffer(1, samples.length, sampleRate);
  buffer.copyToChannel(samples, 0);
  return buffer;
}

/**
 * Queue a buffer to play at `when`; returns end time on the audio clock.
 * @param {AudioContext} ctx
 * @param {AudioBuffer} buffer
 * @param {number} when
 * @returns {number}
 */
function scheduleBuffer(ctx, buffer, when) {
  const src = ctx.createBufferSource();
  src.buffer = buffer;
  src.connect(ctx.destination);
  const startAt = Math.max(when, ctx.currentTime + 0.01);
  src.start(startAt);
  activeSources.push(src);
  src.onended = () => {
    const i = activeSources.indexOf(src);
    if (i >= 0) activeSources.splice(i, 1);
  };
  return startAt + buffer.duration;
}

/**
 * @param {any} engine
 * @param {string} prompt
 * @param {{ voice: string, speed: number }} genOpts
 * @returns {Promise<any>}
 */
async function generateChunk(engine, prompt, genOpts) {
  return engine.generate(prompt, genOpts);
}

/**
 * Speak Simlish orthography with stock Kokoro + custom IPA mapping.
 * Synthesizes clause chunks so playback can start before the full utterance is done.
 * Prefer TextSplitterStream when available; fall back to pipelined generate().
 * @param {string} simlishText
 * @param {{
 *   voice?: string,
 *   speed?: number,
 *   onStatus?: (msg: string) => void,
 *   onEnded?: () => void,
 * }} [opts]
 */
export async function speakSimlish(simlishText, opts = {}) {
  const text = (simlishText || "").trim();
  if (!text) return;

  stopSpeaking();
  const gen = speakGeneration;
  /** @param {string} msg */
  const status = (msg) => {
    if (gen === speakGeneration) opts.onStatus?.(msg);
  };

  const engine = await ensureTts(status);
  if (gen !== speakGeneration) return;

  const voice = opts.voice || DEFAULT_VOICE;
  const speed = opts.speed ?? DEFAULT_SPEED;
  const chunks = splitSpeakChunks(text);
  const ctx = getAudioContext();
  if (ctx.state === "suspended") {
    try {
      await ctx.resume();
    } catch {
      /* autoplay policy */
    }
  }

  status("Synthesizing…");

  const mod = await loadKokoroMod();
  if (gen !== speakGeneration) return;

  const genOpts = { voice, speed };
  let nextWhen = ctx.currentTime;
  let started = false;

  const playRaw = (rawAudio, index, total) => {
    if (gen !== speakGeneration) return;
    const { samples, sampleRate } = rawAudioToSamples(rawAudio);
    const buffer = samplesToBuffer(ctx, samples, sampleRate);
    nextWhen = scheduleBuffer(ctx, buffer, nextWhen);
    if (!started) {
      started = true;
      status("Speaking…");
    } else {
      status(`Speaking… (${index}/${total})`);
    }
  };

  const TextSplitterStream = mod.TextSplitterStream;
  const canStream =
    typeof engine.stream === "function" && typeof TextSplitterStream === "function";

  if (canStream) {
    const splitter = new TextSplitterStream();
    let stream;
    try {
      stream = engine.stream(splitter, genOpts);
    } catch {
      stream = engine.stream(splitter);
    }

    const consumer = (async () => {
      let i = 0;
      for await (const item of stream) {
        if (gen !== speakGeneration) break;
        const audio = item?.audio;
        if (!audio) continue;
        i += 1;
        playRaw(audio, i, chunks.length);
      }
    })();

    for (const chunk of chunks) {
      if (gen !== speakGeneration) break;
      splitter.push(simlishToKokoroInput(chunk));
      if (typeof splitter.flush === "function") splitter.flush();
      await new Promise((r) => setTimeout(r, 0));
    }
    if (typeof splitter.close === "function") splitter.close();
    await consumer;
  } else {
    /** @type {Promise<any> | null} */
    let pending = generateChunk(engine, simlishToKokoroInput(chunks[0]), genOpts);
    for (let i = 0; i < chunks.length; i++) {
      if (gen !== speakGeneration) break;
      const audio = await pending;
      if (gen !== speakGeneration) break;
      if (i + 1 < chunks.length) {
        pending = generateChunk(
          engine,
          simlishToKokoroInput(chunks[i + 1]),
          genOpts,
        );
      } else {
        pending = null;
      }
      playRaw(audio, i + 1, chunks.length);
    }
  }

  if (gen !== speakGeneration) return;

  const endAt = nextWhen;
  while (gen === speakGeneration && ctx.currentTime < endAt - 0.02) {
    await new Promise((r) => setTimeout(r, 50));
  }

  if (gen === speakGeneration) {
    status("Done.");
    opts.onEnded?.();
  }
}
