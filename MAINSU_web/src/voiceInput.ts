type RecognitionResult = {
  0: { transcript: string };
  isFinal: boolean;
};

type BrowserRecognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onstart: (() => void) | null;
  onresult: ((event: { results: ArrayLike<RecognitionResult> }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
};

export type VoiceInput = {
  stop(): void;
  cancel(): void;
};

function recognitionError(code: string) {
  switch (code) {
    case "not-allowed":
    case "service-not-allowed":
      return "瀏覽器未允許語音辨識。請檢查麥克風權限，或使用文字作答。";
    case "audio-capture":
      return "無法讀取麥克風。請檢查輸入裝置，或使用文字作答。";
    case "network":
      return "無法連線至瀏覽器的語音辨識服務。可以重試，或使用文字作答。";
    case "no-speech":
      return "未辨識到語音。請再說一次，或使用文字作答。";
    default:
      return "語音辨識已中斷。可以重試，或使用文字作答。";
  }
}

export function startVoiceInput({
  continuous, onStart, onText, onEnd,
}: {
  continuous: boolean;
  onStart: () => void;
  onText: (text: string) => void;
  onEnd: (text: string, error?: string) => void;
}): VoiceInput {
  type Constructor = new () => BrowserRecognition;
  const browser = window as Window & {
    SpeechRecognition?: Constructor;
    webkitSpeechRecognition?: Constructor;
  };
  const Recognition = browser.SpeechRecognition ?? browser.webkitSpeechRecognition;
  if (!Recognition) throw new Error("這個瀏覽器不支援語音辨識，可以使用文字作答。");

  const recognition = new Recognition();
  let finished = false;
  let stopping = false;
  let stopTimeout: number | undefined;
  let finalText = "";
  let preview = "";
  let prior = "";
  recognition.lang = "zh-TW";
  recognition.continuous = continuous;
  recognition.interimResults = true;

  function release() {
    finished = true;
    window.clearTimeout(stopTimeout);
    recognition.onstart = recognition.onresult = recognition.onerror = recognition.onend = null;
  }

  function finish(error?: string, abort = false) {
    if (finished) return;
    release();
    if (abort) recognition.abort();
    onEnd([prior, finalText || preview].filter(Boolean).join(" "), error);
  }

  recognition.onstart = onStart;
  recognition.onresult = ({ results }) => {
    const segments = Array.from(results);
    finalText = segments.filter((result) => result.isFinal).map((result) => result[0].transcript.trim()).join(" ").trim();
    preview = segments.map((result) => result[0].transcript.trim()).join(" ").trim();
    onText([prior, preview].filter(Boolean).join(" "));
  };
  recognition.onerror = ({ error }) => { if (error === "no-speech" && continuous && !stopping) return; finish(recognitionError(error), true); };
  recognition.onend = () => {
    if (continuous && !stopping && !finished) {
      prior = [prior, finalText || preview].filter(Boolean).join(" "); finalText = preview = "";
      try { recognition.start(); } catch { finish("語音辨識已中斷，請重試。"); }
    } else finish();
  };
  try {
    recognition.start();
  } catch {
    release();
    throw new Error("無法啟動語音辨識。請再試一次，或使用文字作答。");
  }

  return {
    stop() {
      if (stopping || finished) return;
      stopping = true;
      stopTimeout = window.setTimeout(() => finish(undefined, true), 2500);
      recognition.stop();
    },
    cancel() {
      if (finished) return;
      release();
      recognition.abort();
    },
  };
}
