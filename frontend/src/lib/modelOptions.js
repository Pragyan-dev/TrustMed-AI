export const DEFAULT_TEXT_MODEL = 'nvidia/nemotron-3-nano-30b-a3b:free'
export const DEFAULT_VISION_MODEL = 'vertex/medgemma-27b-it'

export const AVAILABLE_TEXT_MODELS = [
  { id: 'nvidia/nemotron-3-nano-30b-a3b:free', label: 'Nemotron 30B' },
  { id: 'vertex/medgemma-27b-it', label: 'MedGemma 27B (Vertex AI)' },
  { id: 'sourceful/riverflow-v2-pro', label: 'Riverflow V2 Pro' },
  { id: 'qwen/qwen3-vl-235b-a22b-thinking', label: 'Qwen 3 VL 235B' },
  { id: 'google/gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro' },
  { id: 'nvidia/llama-nemotron-embed-vl-1b-v2:free', label: 'Nemotron Embed VL 1B' },
]

export const AVAILABLE_VISION_MODELS = [
  { id: 'vertex/medgemma-27b-it', label: 'MedGemma 27B (Vertex AI)' },
  { id: 'google/gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro' },
  { id: 'google/gemini-3-flash-preview', label: 'Gemini 3 Flash' },
  { id: 'z-ai/glm-4.5-air:free', label: 'GLM 4.5 Air' },
  { id: 'meta-llama/llama-3.2-90b-vision-instruct:free', label: 'Llama 90B Vision' },
]
