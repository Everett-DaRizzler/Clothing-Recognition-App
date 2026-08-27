export const API_URL = (process.env.EXPO_PUBLIC_API_URL ?? '').replace(/\/+$/, '');
export const API_CONFIGURED = API_URL.length > 0;

export type ClothingItem = {
  id: string;
  imageId: string;
  name: string;
  brand?: string | null;
  category?: string | null;
  type?: string | null;
  color?: string | null;
  secondaryColors: string[];
  pattern?: string | null;
  fabric?: string | null;
  fit?: string | null;
  style: string[];
  occasion: string[];
  season: string[];
  aiModelId: string;
  aiModelVersion: string;
  aiConfidence: Record<string, number | null>;
  aiPrediction: Record<string, unknown>;
  userCorrected: boolean;
  createdAt: string;
  updatedAt: string;
};

export type Outfit = {
  id: string;
  name: string;
  clothingItemIds: string[];
  clothingItems: ClothingItem[];
  deletedItemIds: string[];
  deletedItemRoles: Record<string, string | null>;
  occasion?: string | null;
  style?: string | null;
  season?: string | null;
  generationMethod: string;
  generationMetadata: Record<string, any>;
  userRating?: number | null;
  createdAt: string;
  updatedAt: string;
};

export type OutfitGeneration = {
  available: boolean;
  items: ClothingItem[];
  clothingItemIds: string[];
  combinationId?: string;
  missingRoles: string[];
  isComplete?: boolean;
  message?: string;
  explanation: string;
  score?: { total: number; components: Record<string, number>; reasons: string[] };
  candidates?: Array<Record<string, any>>;
  rejected?: Array<Record<string, any>>;
  filters?: Record<string, string | null>;
  generationMethod?: string;
};

type ErrorKind = 'configuration' | 'network' | 'timeout' | 'http' | 'invalid-response';

export class ApiError extends Error {
  constructor(public kind: ErrorKind, message: string, public status?: number) {
    super(message);
  }
}

async function requestJson(path: string, init: RequestInit = {}, timeoutMs = 10_000) {
  if (!API_CONFIGURED) throw new ApiError('configuration', 'EXPO_PUBLIC_API_URL is not configured.');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_URL}${path}`, { ...init, signal: controller.signal });
    const body = await response.text();
    if (!response.ok) {
      let detail = '';
      try { detail = JSON.parse(body)?.detail ?? ''; } catch {}
      throw new ApiError('http', detail || `HTTP ${response.status}`, response.status);
    }
    try { return JSON.parse(body); }
    catch { throw new ApiError('invalid-response', 'The backend returned invalid JSON.'); }
  } catch (error: any) {
    if (error instanceof ApiError) throw error;
    if (error?.name === 'AbortError') throw new ApiError('timeout', 'The request timed out.');
    throw new ApiError('network', 'The phone could not reach the development computer.');
  } finally { clearTimeout(timer); }
}

export const getHealth = () => requestJson('/health', {}, 5_000);
export const getModels = () => requestJson('/models', {}, 5_000);
export const getWardrobe = (search = '', category = 'All') => requestJson(`/wardrobe?search=${encodeURIComponent(search)}&category=${encodeURIComponent(category)}`, {}, 10_000) as Promise<ClothingItem[]>;
export const getWardrobeItem = (id: string) => requestJson(`/wardrobe/${encodeURIComponent(id)}`, {}, 10_000) as Promise<ClothingItem>;

export function imageUrl(imageId: string, variant: 'thumbnail' | 'original' = 'thumbnail') {
  return `${API_URL}/images/${encodeURIComponent(imageId)}/${variant}`;
}

export function analyzePhoto(uri: string) {
  const form = new FormData();
  form.append('file', { uri, name: 'clothing.jpg', type: 'image/jpeg' } as any);
  return requestJson('/analyze', { method: 'POST', body: form }, 190_000);
}

export function saveWardrobeItem(values: Record<string, unknown>) {
  return requestJson('/wardrobe', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values) }, 15_000) as Promise<ClothingItem>;
}

export function updateWardrobeItem(id: string, values: Record<string, unknown>) {
  return requestJson(`/wardrobe/${encodeURIComponent(id)}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values) }, 15_000) as Promise<ClothingItem>;
}

export function deleteWardrobeItem(id: string) {
  return requestJson(`/wardrobe/${encodeURIComponent(id)}`, { method: 'DELETE' }, 15_000);
}

export const getOutfits = () => requestJson('/outfits', {}, 10_000) as Promise<Outfit[]>;
export const getOutfit = (id: string) => requestJson(`/outfits/${encodeURIComponent(id)}`, {}, 10_000) as Promise<Outfit>;
export function generateOutfit(values: Record<string, unknown>) {
  return requestJson('/outfits/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values) }, 15_000) as Promise<OutfitGeneration>;
}
export function saveOutfit(values: Record<string, unknown>) {
  return requestJson('/outfits', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values) }, 15_000) as Promise<Outfit>;
}
export function updateOutfit(id: string, values: Record<string, unknown>) {
  return requestJson(`/outfits/${encodeURIComponent(id)}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values) }, 15_000) as Promise<Outfit>;
}
export function replaceOutfitItem(id: string, role: string, clothingItemId: string) {
  return requestJson(`/outfits/${encodeURIComponent(id)}/replace`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ role, clothingItemId }) }, 15_000) as Promise<Outfit>;
}
export function rateOutfit(id: string, userRating: number | null) {
  return requestJson(`/outfits/${encodeURIComponent(id)}/rating`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ userRating }) }, 15_000) as Promise<Outfit>;
}
export const getTestOutfitWardrobe = () => requestJson('/developer/outfit-test-wardrobe', {}, 10_000) as Promise<{ items: ClothingItem[]; notice: string }>;

export function saveCorrection(imageId: string, attribute: string, originalAIValue: unknown, correctedValue: unknown) {
  return requestJson(`/corrections?image_id=${encodeURIComponent(imageId)}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ attribute, originalAIValue, correctedValue }),
  });
}

export function friendlyApiError(error: unknown) {
  const apiError = error instanceof ApiError ? error : new ApiError('network', 'Unknown connection error.');
  if (apiError.kind === 'configuration') return 'Backend URL is not configured. Set EXPO_PUBLIC_API_URL in mobile/.env.local and restart Expo.';
  if (apiError.kind === 'timeout') return 'The request timed out. The AI may still be loading. Keep the backend running and try again.';
  if (apiError.kind === 'http') return apiError.status && apiError.status >= 500 ? 'The local backend could not complete that request. Check the backend terminal and try again.' : `The backend returned HTTP ${apiError.status ?? 'error'}: ${apiError.message}`;
  if (apiError.kind === 'invalid-response') return apiError.message;
  return `Cannot connect to the development computer at ${API_URL || 'the configured URL'}.\n\nMake sure:\n1. Your iPhone and computer are on the same Wi-Fi.\n2. The backend is running.\n3. EXPO_PUBLIC_API_URL contains the correct computer IP and port.\n4. Windows Firewall allows TCP port 8000.`;
}
