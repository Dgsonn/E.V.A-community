"use client";

import { useRef, useState } from "react";
import { api } from "./api";

// Đọc thẳng mẫu âm thanh thô (PCM) qua Web Audio API thay vì MediaRecorder — MediaRecorder trên
// WebKit/Safari (bắt buộc dùng trên MỌI trình duyệt iOS, kể cả Chrome) có lúc không bắn sự kiện
// "onstop" dù đã gọi .stop(), khiến việc ghi âm treo vĩnh viễn không cách nào bắt lỗi được từ
// bên ngoài. Web Audio API (AudioContext + ScriptProcessorNode) không đi qua vòng đời ghi-file
// của MediaRecorder nên né được hẳn lớp lỗi đó — đổi lại phải tự resample + tự đóng gói WAV,
// việc mà trước đây encodeWav() làm sau khi giải mã ngược file MediaRecorder ghi ra.

const TARGET_RATE = 16000;
const MAX_RECORD_SECS = 60; // an toàn — tự dừng nếu lỡ giữ quá lâu, tránh ghi vô hạn tốn RAM

function floatTo16BitPCM(samples: Float32Array): Int16Array {
  const out = new Int16Array(samples.length);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

function encodeWavFromPCM(pcm: Int16Array, sampleRate: number): Blob {
  const headerLen = 44;
  const buffer = new ArrayBuffer(headerLen + pcm.length * 2);
  const view = new DataView(buffer);
  const writeStr = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
  };
  writeStr(0, "RIFF");
  view.setUint32(4, 36 + pcm.length * 2, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  writeStr(36, "data");
  view.setUint32(40, pcm.length * 2, true);
  let offset = 44;
  for (let i = 0; i < pcm.length; i++, offset += 2) {
    view.setInt16(offset, pcm[i], true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

// AudioContext luôn chạy ở sample rate riêng của thiết bị (thường 44100/48000, trình duyệt
// không cho ép về 16000 thẳng) — resample lại bằng OfflineAudioContext, cùng kỹ thuật cũ đã
// dùng khi còn giải mã ngược file MediaRecorder.
async function resampleTo16k(samples: Float32Array, srcRate: number): Promise<Float32Array> {
  if (srcRate === TARGET_RATE) return samples;
  const offlineCtx = new OfflineAudioContext(1, Math.ceil((samples.length * TARGET_RATE) / srcRate), TARGET_RATE);
  const buffer = offlineCtx.createBuffer(1, samples.length, srcRate);
  buffer.copyToChannel(samples as Float32Array<ArrayBuffer>, 0);
  const source = offlineCtx.createBufferSource();
  source.buffer = buffer;
  source.connect(offlineCtx.destination);
  source.start(0);
  const rendered = await offlineCtx.startRendering();
  return rendered.getChannelData(0);
}

export function useVoiceRecorder() {
  const [isRecording, setIsRecording] = useState(false);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const muteGainRef = useRef<GainNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Float32Array[]>([]);
  const maxDurTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const start = async (): Promise<string | null> => {
    api.debugLog("start() (Web Audio API) bắt đầu.");

    // Tạo AudioContext TRƯỚC getUserMedia, càng gần lúc bấm nút (user gesture) càng chắc chắn
    // Safari không chặn — 1 số bản Safari cũ yêu cầu AudioContext phải khởi tạo trong cùng
    // tick với thao tác chạm của người dùng.
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const audioCtx = new AudioCtx();
    if (audioCtx.state === "suspended") {
      await audioCtx.resume();
    }
    audioCtxRef.current = audioCtx;
    api.debugLog(`AudioContext tạo xong, state=${audioCtx.state}, sampleRate=${audioCtx.sampleRate}`);

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      api.debugLog("getUserMedia OK, đã có stream.");
    } catch (err) {
      api.debugLog(`getUserMedia LỖI: ${err instanceof Error ? err.message : String(err)}`);
      await audioCtx.close();
      audioCtxRef.current = null;
      return "Không dùng được mic trên trình duyệt (bị từ chối quyền hoặc không có thiết bị).";
    }
    streamRef.current = stream;

    const source = audioCtx.createMediaStreamSource(stream);
    sourceRef.current = source;

    // bufferSize 4096 ~ 256ms mỗi lần ở 16kHz gốc — đủ nhỏ để không giật, đủ lớn để đỡ tốn CPU
    // gọi callback liên tục. Chỉ hỗ trợ 1 kênh vào/ra vì EVA chỉ cần mono.
    const processor = audioCtx.createScriptProcessor(4096, 1, 1);
    processorRef.current = processor;
    chunksRef.current = [];
    processor.onaudioprocess = (e) => {
      // .getChannelData trả về buffer TÁI SỬ DỤNG bởi trình duyệt cho lần gọi kế tiếp — bắt buộc
      // phải copy (new Float32Array(input)) chứ không giữ thẳng tham chiếu, không thì dữ liệu cũ
      // sẽ bị ghi đè trước khi đem đi ghép.
      const input = e.inputBuffer.getChannelData(0);
      chunksRef.current.push(new Float32Array(input));
    };

    // Một số trình duyệt (đặc biệt Safari) chỉ thực sự gọi onaudioprocess khi node có nối tới
    // destination (loa) — nối qua 1 GainNode mức 0 để không phát ra tiếng thật (tránh vọng/hú lại
    // chính giọng mình qua loa) nhưng vẫn giữ audio graph "sống".
    const muteGain = audioCtx.createGain();
    muteGain.gain.value = 0;
    muteGainRef.current = muteGain;
    source.connect(processor);
    processor.connect(muteGain);
    muteGain.connect(audioCtx.destination);

    api.debugLog("ScriptProcessorNode đã nối xong, bắt đầu nhận audio.");
    setIsRecording(true);

    maxDurTimerRef.current = setTimeout(() => {
      api.debugLog(`Đã ghi quá ${MAX_RECORD_SECS}s, tự dừng an toàn.`);
    }, MAX_RECORD_SECS * 1000);

    return null;
  };

  // Trả về WAV blob đã ghi, hoặc null nếu không ghi được gì.
  const stop = async (): Promise<Blob | null> => {
    api.debugLog("stop() (Web Audio API) được gọi.");
    if (maxDurTimerRef.current) {
      clearTimeout(maxDurTimerRef.current);
      maxDurTimerRef.current = null;
    }

    const audioCtx = audioCtxRef.current;
    const processor = processorRef.current;
    const source = sourceRef.current;
    const muteGain = muteGainRef.current;
    const stream = streamRef.current;

    setIsRecording(false);

    if (!audioCtx || !processor || !source) {
      api.debugLog("stop(): chưa từng start() thành công, trả về null.");
      return null;
    }

    // Ngắt kết nối node NGAY (đồng bộ, không như MediaRecorder.stop() phải chờ sự kiện bất đồng
    // bộ mới biết đã dừng hẳn chưa) — đây chính là điểm khác biệt giúp né lỗi "treo vĩnh viễn".
    processor.disconnect();
    source.disconnect();
    muteGain?.disconnect();
    stream?.getTracks().forEach((t) => t.stop());

    const chunks = chunksRef.current;
    chunksRef.current = [];
    const totalLen = chunks.reduce((sum, c) => sum + c.length, 0);
    const srcRate = audioCtx.sampleRate;
    api.debugLog(`Đã ghi ${totalLen} mẫu @ ${srcRate}Hz gốc.`);

    audioCtxRef.current = null;
    processorRef.current = null;
    sourceRef.current = null;
    muteGainRef.current = null;
    streamRef.current = null;

    if (totalLen === 0) {
      await audioCtx.close();
      return null;
    }

    const merged = new Float32Array(totalLen);
    let offset = 0;
    for (const c of chunks) {
      merged.set(c, offset);
      offset += c.length;
    }

    try {
      const resampled = await resampleTo16k(merged, srcRate);
      api.debugLog(`Resample xong: ${resampled.length} mẫu @ ${TARGET_RATE}Hz.`);
      const pcm = floatTo16BitPCM(resampled);
      const wav = encodeWavFromPCM(pcm, TARGET_RATE);
      api.debugLog(`WAV encode xong: ${wav.size} bytes.`);
      await audioCtx.close();
      return wav;
    } catch (err) {
      api.debugLog(`Lỗi resample/encode: ${err instanceof Error ? err.message : String(err)}`);
      await audioCtx.close();
      throw err;
    }
  };

  return { isRecording, start, stop };
}
