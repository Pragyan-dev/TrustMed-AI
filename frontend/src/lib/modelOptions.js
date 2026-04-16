export const DEFAULT_TEXT_MODEL = 'google/gemini-2.0-flash-exp:free'
export const DEFAULT_VISION_MODEL = 'google/gemini-2.0-flash-exp:free'

export const AVAILABLE_TEXT_MODELS = [
  { id: 'google/gemini-2.0-flash-exp:free', label: 'Gemini 2.0 Flash (Free)' },
  { id: 'nvidia/llama-3.1-nemotron-70b-instruct:free', label: 'Llama Nemotron 70B (Free)' },
  { id: 'google/gemma-2-9b-it:free', label: 'Gemma 2 9B (Free)' },
  { id: 'mistralai/mistral-7b-instruct:free', label: 'Mistral 7B (Free)' },
  { id: 'google/gemini-2.0-flash-001', label: 'Gemini 2.0 Flash' },
  { id: 'google/gemini-pro-1.5', label: 'Gemini 1.5 Pro' },
]

export const AVAILABLE_VISION_MODELS = [
  { id: 'google/gemini-2.0-flash-exp:free', label: 'Gemini 2.0 Flash (Free)' },
  { id: 'meta-llama/llama-3.2-90b-vision-instruct:free', label: 'Llama 90B Vision (Free)' },
  { id: 'google/gemini-2.0-flash-001', label: 'Gemini 2.0 Flash' },
  { id: 'google/gemini-pro-1.5', label: 'Gemini 1.5 Pro' },
]
