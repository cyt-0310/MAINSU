export type SpeechMetrics = {
  rate: number | null;
  fillers: Record<string, number>;
  pauses: { start: number; duration: number }[];
  audibleSeconds: number;
  sufficient: boolean;
  recognitionWarning?: string;
};
export async function monitorAudio(onLevel: (level: number) => void) {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const context = new AudioContext();
  const analyser = context.createAnalyser();
  analyser.fftSize = 1024;
  context.createMediaStreamSource(stream).connect(analyser);
  const samples = new Float32Array(analyser.fftSize);
  const start = performance.now();
  let last = start, silence: number | null = null, heard = false, audible = 0;
  const pauses: SpeechMetrics["pauses"] = [];
  let recorder: MediaRecorder | undefined;
  try {
    recorder = new MediaRecorder(stream);
    recorder.ondataavailable = () => {}; // Raw audio is discarded, not uploaded or saved.
    recorder.start(1000);
  } catch { /* acoustic analysis can proceed without recorder */ }
  const tick = window.setInterval(() => {
    analyser.getFloatTimeDomainData(samples);
    const rms = Math.sqrt(samples.reduce((sum, x) => sum + x*x, 0) / samples.length);
    const now = performance.now();
    onLevel(Math.min(100, Math.round(rms * 500)));
    if (rms >= .018) {
      audible += (now-last)/1000;
      if (heard && silence !== null && now-silence >= 1000) pauses.push({start:(silence-start)/1000,duration:(now-silence)/1000});
      heard = true; silence = null;
    } else if (heard && silence === null) silence = now;
    last = now;
  }, 100);
  let stopped = false;
  return {
    stop(text = "", duration = 0, recognitionWarning?: string): SpeechMetrics {
      if (!stopped) {
        stopped = true; clearInterval(tick);
        if (recorder?.state === "recording") recorder.stop();
        stream.getTracks().forEach(track => track.stop());
        void context.close(); onLevel(0);
      }
      const count = Array.from(text.replace(/[^\p{L}\p{N}]/gu, "")).length;
      const fillers = Object.fromEntries(["嗯","呃","然後","那個","就是"].map(word => [word,text.split(word).length-1]));
      return {rate: duration > 0 && count > 0 ? Math.round(count*60/duration) : null, fillers, pauses, audibleSeconds: Math.round(audible*10)/10, sufficient: heard && count > 0 && !recognitionWarning, recognitionWarning};
    }
  };
}
export function readQuestion(text: string, done: () => void) {
  if (!("speechSynthesis" in window)) { done(); return () => {}; }
  const speech = new SpeechSynthesisUtterance(text);
  speech.lang = "zh-TW";
  let finished = false;
  const finish = () => { if (!finished) { finished = true; done(); } };
  speech.onend = finish; speech.onerror = finish;
  window.speechSynthesis.speak(speech);
  return () => { finished = true; window.speechSynthesis.cancel(); };
}
