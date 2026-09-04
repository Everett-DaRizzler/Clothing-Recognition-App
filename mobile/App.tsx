import React, { useEffect, useMemo, useState } from 'react';
import { Alert, BackHandler, FlatList, Image, KeyboardAvoidingView, Platform, ScrollView, StyleSheet, TouchableOpacity, View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import Ionicons from '@expo/vector-icons/Ionicons';
import { ThemeProvider, Palette, useTheme } from './src/theme';
import { AppChrome, MainTab } from './src/components/AppChrome';
import { ThemePicker } from './src/components/ThemePicker';
import { Button, Text, TextInput } from './src/components/ui';
import * as ImagePicker from 'expo-image-picker';
import { API_CONFIGURED, API_URL, ClothingItem, Outfit, OutfitGeneration, PersonalizationProfile, analyzePhoto, deleteWardrobeItem, friendlyApiError, generateOutfit, getHealth, getModels, getOutfit, getOutfits, getPersonalization, getPersonalizationLab, getWardrobe, imageUrl, markOutfitWorn, rateOutfit, replaceOutfitItem, resetLearnedPreferences, saveCorrection, saveOutfit, saveWardrobeItem, sendOutfitFeedback, setFavorite, updatePersonalization, updateWardrobeItem } from './src/api';

const attributes = ['category', 'type', 'color', 'pattern', 'fabric', 'fit', 'style', 'occasion', 'season'];
const categoryFilters = ['All', 'Tops', 'Bottoms', 'Shoes', 'Outerwear', 'Accessories'];
const categoryChoices = ['Top', 'Bottom', 'Shoes', 'Outerwear', 'Accessories'];
const colorChoices = ['Black', 'White', 'Navy', 'Blue', 'Brown', 'Gray', 'Green', 'Red', 'Beige'];
const patternChoices = ['Solid', 'Striped', 'Plaid', 'Graphic', 'Floral', 'Printed'];
const fabricChoices = ['Cotton', 'Denim', 'Wool', 'Leather', 'Linen', 'Synthetic', 'Knit'];
const fitChoices = ['Slim', 'Regular', 'Relaxed', 'Oversized'];
const clothingStyleChoices = ['Casual', 'Smart casual', 'Formal', 'Sporty', 'Minimal', 'Vintage', 'Streetwear'];
const clothingOccasionChoices = ['Everyday', 'Work', 'Formal', 'Travel', 'Workout', 'Outdoor'];
const clothingSeasonChoices = ['Spring', 'Summer', 'Fall', 'Winter', 'All season'];
const outfitOccasions = ['Any', 'Everyday', 'School', 'Date', 'Casual', 'Formal', 'Work', 'Party'];
const outfitStyles = ['Any', 'Casual', 'Smart Casual', 'Formal', 'Streetwear', 'Sporty', 'Classic', 'Minimal', 'Preppy'];
const outfitSeasons = ['Any', 'Spring', 'Summer', 'Fall', 'Winter'];

type Screen = 'wardrobe' | 'review' | 'detail' | 'edit' | 'lab' | 'outfits' | 'generate' | 'result' | 'outfitDetail' | 'outfitLab' | 'personalization' | 'personalizationLab' | 'profile' | 'settings';
type Draft = Record<string, any>;
type Connection = { state: 'idle' | 'checking' | 'connected' | 'error'; detail?: string };

const arrayOrEmpty = (value: any) => Array.isArray(value) ? value : value ? [value] : [];
const draftFrom = (value: any): Draft => ({
  name: value?.name ?? '', brand: value?.brand ?? '', category: value?.category ?? '', type: value?.type ?? '', color: value?.color ?? '',
  secondaryColors: arrayOrEmpty(value?.secondaryColors), pattern: value?.pattern ?? '', fabric: value?.fabric ?? '', fit: value?.fit ?? '',
  style: arrayOrEmpty(value?.style), occasion: arrayOrEmpty(value?.occasion ?? value?.occasions), season: arrayOrEmpty(value?.season ?? value?.seasons),
});
const displayValue = (value: any) => Array.isArray(value) ? value.join(' · ') || 'Not detected' : value || 'Not detected';
const roleForItem = (item: ClothingItem) => {
  const text = `${item.category ?? ''} ${item.type ?? ''} ${item.name ?? ''}`.toLowerCase();
  if (/(shoe|sneaker|boot|loafer|sandal|heel|slipper)/.test(text)) return 'shoes';
  if (/(outerwear|jacket|coat|parka|blazer|cardigan|vest)/.test(text)) return 'outerwear';
  if (/(accessor|belt|hat|scarf|bag|watch|tie)/.test(text)) return 'accessory';
  if (/(bottom|pant|jean|short|skirt|trouser|chino)/.test(text)) return 'bottom';
  if (/(top|shirt|tee|t-shirt|polo|blouse|sweater|hoodie|tank)/.test(text)) return 'top';
  return undefined;
};

function Chip({ label, selected, onPress }: { label: string; selected: boolean; onPress: () => void }) {
  const s = useStyles();
  return <TouchableOpacity accessibilityRole="button" accessibilityState={{ selected }} onPress={onPress} hitSlop={{ top: 4, bottom: 4, left: 2, right: 2 }} style={[s.chip, selected && s.chipSelected]}><Text style={selected ? s.chipTextSelected : s.chipText}>{label}</Text></TouchableOpacity>;
}

function WardrobeImage({ imageId, variant = 'thumbnail', style }: { imageId: string; variant?: 'thumbnail' | 'original'; style: any }) {
  const s = useStyles();
  const [failed, setFailed] = useState(false);
  if (!imageId || failed) return <View style={[style, s.imageFallback]}><Text style={s.imageFallbackText}>{imageId ? 'Photo unavailable' : 'Test item'}</Text></View>;
  return <Image source={{ uri: imageUrl(imageId, variant) }} style={style} onError={() => setFailed(true)} />;
}

function OutfitItemCard({ item, onReplace, missing = false }: { item: ClothingItem; onReplace?: () => void; missing?: boolean }) {
  const s = useStyles();
  return <View style={s.outfitItemCard}><WardrobeImage imageId={item.imageId} style={s.outfitImage} /><View style={s.outfitItemText}><Text style={s.itemRole}>{(roleForItem(item) ?? 'item').toUpperCase()}</Text><Text style={s.outfitItemName} numberOfLines={2}>{item.name}</Text><Text style={s.cardMeta} numberOfLines={2}>{displayValue(item.color)} · {displayValue(item.style)}</Text>{missing ? <Text style={s.errorText}>This item was deleted</Text> : null}{onReplace ? <Button title="Replace" onPress={onReplace} /> : null}</View></View>;
}

function WardrobeApp() {
  const { theme: { colors }, ready } = useTheme();
  const s = useStyles();
  const [navigation, setNavigation] = useState<Screen[]>(['wardrobe']);
  const screen = navigation[navigation.length - 1];
  const setScreen = (next: Screen) => setNavigation(current => {
    if (current[current.length - 1] === next) return current;
    const existing = current.lastIndexOf(next);
    return existing >= 0 ? current.slice(0, existing + 1) : [...current, next];
  });
  const goBack = () => setNavigation(current => current.length > 1 ? current.slice(0, -1) : current);
  const switchTab = (tab: MainTab) => { setNavigation([tab]); setReplaceRole(undefined); };
  const routeTab = (route: Screen): MainTab | undefined =>
    ['outfits', 'generate', 'result', 'outfitDetail'].includes(route) ? 'outfits' :
    ['profile', 'personalization'].includes(route) ? 'profile' :
    ['wardrobe', 'detail', 'edit', 'review'].includes(route) ? 'wardrobe' : undefined;
  const activeTab = [...navigation].reverse().map(routeTab).find(Boolean) as MainTab || 'wardrobe';
  useEffect(() => {
    const subscription = BackHandler.addEventListener('hardwareBackPress', () => {
      if (navigation.length <= 1) return false;
      goBack();
      return true;
    });
    return () => subscription.remove();
  }, [navigation.length]);
  const [items, setItems] = useState<ClothingItem[]>([]);
  const [selected, setSelected] = useState<ClothingItem>();
  const [uri, setUri] = useState<string>();
  const [result, setResult] = useState<any>();
  const [draft, setDraft] = useState<Draft>({});
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('All');
  const [loading, setLoading] = useState(false);
  const [wardrobeError, setWardrobeError] = useState('');
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState('');
  const [analysisError, setAnalysisError] = useState('');
  const [saveError, setSaveError] = useState('');
  const [saveBusy, setSaveBusy] = useState(false);
  const [labMode, setLabMode] = useState(false);
  const [corrections, setCorrections] = useState<Record<string, string>>({});
  const [connection, setConnection] = useState<Connection>({ state: 'idle' });
  const [models, setModels] = useState<any[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsError, setModelsError] = useState('');
  const [outfits, setOutfits] = useState<Outfit[]>([]);
  const [outfitsError, setOutfitsError] = useState('');
  const [outfitLoading, setOutfitLoading] = useState(false);
  const [outfitResult, setOutfitResult] = useState<OutfitGeneration>();
  const [selectedOutfit, setSelectedOutfit] = useState<Outfit>();
  const [outfitOccasion, setOutfitOccasion] = useState('Any');
  const [outfitStyle, setOutfitStyle] = useState('Any');
  const [outfitSeason, setOutfitSeason] = useState('Any');
  const [anchorItem, setAnchorItem] = useState<ClothingItem>();
  const [recentCombinations, setRecentCombinations] = useState<string[]>([]);
  const [replaceRole, setReplaceRole] = useState<string>();
  const [testLab, setTestLab] = useState(false);
  const [outfitResultSource, setOutfitResultSource] = useState<'wardrobe' | 'test'>('wardrobe');
  const [personalization, setPersonalization] = useState<PersonalizationProfile>();
  const [personalizationError, setPersonalizationError] = useState('');
  const [preferredStyles, setPreferredStyles] = useState<string[]>([]);
  const [dislikedStyles, setDislikedStyles] = useState<string[]>([]);

  const refreshWardrobe = async () => { setLoading(true); try { setItems(await getWardrobe(search, category)); setWardrobeError(''); } catch (error) { setWardrobeError(friendlyApiError(error)); } finally { setLoading(false); } };
  const refreshOutfits = async () => { setOutfitLoading(true); try { setOutfits(await getOutfits()); setOutfitsError(''); } catch (error) { setOutfitsError(friendlyApiError(error)); } finally { setOutfitLoading(false); } };
  useEffect(() => { if ((screen === 'wardrobe' || screen === 'generate') && API_CONFIGURED) { const timer = setTimeout(refreshWardrobe, 250); return () => clearTimeout(timer); } }, [screen, search, category]);
  useEffect(() => { if (screen === 'outfits' && API_CONFIGURED) refreshOutfits(); }, [screen]);
  useEffect(() => { if (screen !== 'lab' || !API_CONFIGURED) return; setModelsLoading(true); setModelsError(''); getModels().then(setModels).catch(error => setModelsError(friendlyApiError(error))).finally(() => setModelsLoading(false)); }, [screen]);
  const refreshPersonalization = async (developer = false) => { try { const profile = developer ? await getPersonalizationLab() : await getPersonalization(); setPersonalization(profile); setPreferredStyles(profile.explicit?.preferredStyles ?? []); setDislikedStyles(profile.explicit?.dislikedStyles ?? []); setPersonalizationError(''); } catch (error) { setPersonalizationError(friendlyApiError(error)); } };
  useEffect(() => { if ((screen === 'personalization' || screen === 'personalizationLab' || screen === 'profile') && API_CONFIGURED) refreshPersonalization(screen === 'personalizationLab'); }, [screen]);

  const pick = async (camera = false, fromLab = false) => { const permission = camera ? await ImagePicker.requestCameraPermissionsAsync() : await ImagePicker.requestMediaLibraryPermissionsAsync(); if (!permission.granted) return Alert.alert('Permission needed', 'Allow photo access in iPhone Settings.'); const selection = camera ? await ImagePicker.launchCameraAsync({ mediaTypes: ['images'], quality: 0.9 }) : await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.9 }); if (!selection.canceled) { setUri(selection.assets[0].uri); setResult(undefined); setDraft({}); setAnalysisError(''); setSaveError(''); setLabMode(fromLab); setScreen('review'); } };
  const analyze = async () => { if (!uri) return; setBusy(true); setAnalysisError(''); setStage('Uploading photo…'); try { setStage('Analyzing your clothing locally…'); const analysis = await analyzePhoto(uri); setResult(analysis); setDraft(draftFrom(analysis)); setStage(''); } catch (error) { setAnalysisError(friendlyApiError(error)); setStage(''); } finally { setBusy(false); } };
  const testConnection = async () => { setConnection({ state: 'checking' }); try { const health = await getHealth(); setConnection({ state: 'connected', detail: `${health.modelName} · ${health.modelCached ? 'Model cached locally' : 'Model cache not found'}` }); } catch (error) { setConnection({ state: 'error', detail: friendlyApiError(error) }); } };
  const savePreferences = async () => { try { setPersonalization(await updatePersonalization({ preferredStyles, dislikedStyles })); Alert.alert('Preferences saved', 'Future outfit rankings will use these choices.'); } catch (error) { setPersonalizationError(friendlyApiError(error)); } };
  const feedbackFor = async (action: 'like' | 'dislike', outfitId?: string) => { const payload: Record<string, unknown> = { action, outfitId, generationId: outfitId ? undefined : outfitResult?.generationId, clothingItemIds: outfitId ? undefined : outfitResult?.clothingItemIds, occasion: outfitId ? undefined : outfitOccasion === 'Any' ? null : outfitOccasion, style: outfitId ? undefined : outfitStyle === 'Any' ? null : outfitStyle, season: outfitId ? undefined : outfitSeason === 'Any' ? null : outfitSeason }; if (action === 'dislike') { Alert.alert('What did you dislike?', 'This is optional and helps keep the signal understandable.', [{ text: 'Skip', onPress: () => sendOutfitFeedback(payload).then(() => refreshPersonalization()).catch(error => Alert.alert('Feedback not saved', friendlyApiError(error))) }, ...['Colors', 'Style', 'One clothing item', 'Too formal', 'Too casual', "Just don't like it"].map(reason => ({ text: reason, onPress: () => sendOutfitFeedback({ ...payload, reason: reason.toLowerCase() }).then(() => refreshPersonalization()).catch(error => Alert.alert('Feedback not saved', friendlyApiError(error))) }))]); } else { try { await sendOutfitFeedback(payload); Alert.alert('Thanks', 'I’ll use that preference in future rankings.'); refreshPersonalization(); } catch (error) { Alert.alert('Feedback not saved', friendlyApiError(error)); } } };
  const toggleFavorite = async () => { if (!selected) return; try { const updated = await setFavorite(selected.id, !selected.isFavorite); setSelected(updated); setItems(current => current.map(item => item.id === updated.id ? updated : item)); } catch (error) { Alert.alert('Favorite not saved', friendlyApiError(error)); } };
  const saveNewItem = async () => { if (!result || saveBusy) return; setSaveBusy(true); setSaveError(''); try { await saveWardrobeItem({ ...draft, imageId: result.imageId, modelId: result.modelId, modelVersion: result.modelVersion, confidence: result.confidence, rawResponse: result.rawResponse, inferenceTimeMs: result.inferenceTimeMs, parseSuccess: result.parseSuccess }); setScreen('wardrobe'); Alert.alert('Added to wardrobe.', 'Your clothing item is ready to browse.'); refreshWardrobe().catch(() => undefined); } catch (error) { setSaveError(friendlyApiError(error)); } finally { setSaveBusy(false); } };
  const saveItemEdits = async () => { if (!selected || saveBusy) return; setSaveBusy(true); setSaveError(''); try { const updated = await updateWardrobeItem(selected.id, draft); setSelected(updated); setScreen('detail'); refreshWardrobe().catch(() => undefined); } catch (error) { setSaveError(friendlyApiError(error)); } finally { setSaveBusy(false); } };
  const confirmDelete = () => { if (!selected) return; Alert.alert('Delete clothing item?', 'The saved wardrobe record will be removed. Your original image and analysis history will remain available.', [{ text: 'Cancel', style: 'cancel' }, { text: 'Delete', style: 'destructive', onPress: async () => { try { await deleteWardrobeItem(selected.id); setItems(current => current.filter(item => item.id !== selected.id)); setSelected(undefined); setScreen('wardrobe'); refreshWardrobe().catch(() => undefined); } catch (error) { Alert.alert('Delete failed', friendlyApiError(error)); } } }]); };
  const updateDraft = (key: string, value: any) => setDraft(current => ({ ...current, [key]: value }));
  const toggleDraftArray = (key: string, value: string) => updateDraft(key, arrayOrEmpty(draft[key]).includes(value) ? arrayOrEmpty(draft[key]).filter((item: string) => item !== value) : [...arrayOrEmpty(draft[key]), value]);
  const renderChoice = (label: string, key: string, choices: string[]) => <View><Text style={s.fieldLabel}>{label}</Text><View style={s.chips}>{choices.map(choice => <Chip key={choice} label={choice} selected={draft[key] === choice} onPress={() => updateDraft(key, choice)} />)}</View><TextInput value={draft[key] ?? ''} onChangeText={value => updateDraft(key, value)} placeholder={`Enter ${label.toLowerCase()} if needed`} style={s.input} /></View>;
  const renderMultiChoice = (label: string, key: string, choices: string[]) => <View><Text style={s.fieldLabel}>{label}</Text><View style={s.chips}>{choices.map(choice => <Chip key={choice} label={choice} selected={arrayOrEmpty(draft[key]).includes(choice)} onPress={() => toggleDraftArray(key, choice)} />)}</View></View>;
  const renderEditor = () => <View><Text style={s.fieldLabel}>Name</Text><TextInput value={draft.name ?? ''} onChangeText={value => updateDraft('name', value)} placeholder="e.g. Navy Polo" style={s.input} /><Text style={s.fieldLabel}>Brand (optional)</Text><TextInput value={draft.brand ?? ''} onChangeText={value => updateDraft('brand', value)} placeholder="Add manually if known" style={s.input} />{renderChoice('Category', 'category', categoryChoices)}<Text style={s.fieldLabel}>Type</Text><TextInput value={draft.type ?? ''} onChangeText={value => updateDraft('type', value)} placeholder="e.g. polo, jeans, boots" style={s.input} />{renderChoice('Color', 'color', colorChoices)}{renderChoice('Pattern', 'pattern', patternChoices)}{renderChoice('Fabric', 'fabric', fabricChoices)}{renderChoice('Fit', 'fit', fitChoices)}{renderMultiChoice('Style', 'style', clothingStyleChoices)}{renderMultiChoice('Occasions', 'occasion', clothingOccasionChoices)}{renderMultiChoice('Seasons', 'season', clothingSeasonChoices)}</View>;
  const renderGuidance = () => <View style={s.guidance}><Text style={s.guidanceTitle}>Photo tips</Text><Text>• Lay the item flat or hang it up.</Text><Text>• Make sure the entire item is visible.</Text><Text>• Use good lighting and avoid other clothing in frame.</Text></View>;

  const runGeneration = async (regenerate = false, sourceOverride?: 'wardrobe' | 'test', destination: Screen = 'result') => { setOutfitLoading(true); const source = sourceOverride ?? (testLab ? 'test' : 'wardrobe'); try { const generated = await generateOutfit({ occasion: outfitOccasion === 'Any' ? null : outfitOccasion, style: outfitStyle === 'Any' ? null : outfitStyle, season: outfitSeason === 'Any' ? null : outfitSeason, anchorItemId: anchorItem?.id ?? null, excludeCombinationIds: regenerate ? recentCombinations : [], source, debug: true }); setOutfitResult(generated); setOutfitResultSource(source); if (generated.combinationId) setRecentCombinations(current => [...current.filter(id => id !== generated.combinationId), generated.combinationId!].slice(-6)); setScreen(destination); } catch (error) { Alert.alert('Could not generate outfit', friendlyApiError(error)); } finally { setOutfitLoading(false); } };
  const saveGeneratedOutfit = async () => { if (!outfitResult?.available || outfitResultSource === 'test') return; setSaveBusy(true); try { const saved = await saveOutfit({ name: `${outfitStyle === 'Any' ? 'New' : outfitStyle} Outfit`, clothingItemIds: outfitResult.clothingItemIds, occasion: outfitOccasion === 'Any' ? null : outfitOccasion, style: outfitStyle === 'Any' ? null : outfitStyle, season: outfitSeason === 'Any' ? null : outfitSeason, generationMethod: 'deterministic', generationMetadata: { score: outfitResult.score, combinationId: outfitResult.combinationId, explanation: outfitResult.explanation } }); setSelectedOutfit(saved); setScreen('outfitDetail'); Alert.alert('Outfit saved', 'You can find it in Saved Outfits.'); } catch (error) { Alert.alert('Could not save outfit', friendlyApiError(error)); } finally { setSaveBusy(false); } };
  const updateGeneratedItem = (role: string, item: ClothingItem) => { if (!outfitResult) return; const next = outfitResult.items.map(existing => roleForItem(existing) === role ? item : existing); setOutfitResult({ ...outfitResult, items: next, clothingItemIds: next.map(itemValue => itemValue.id), combinationId: next.map(itemValue => itemValue.id).sort().join('|') }); setReplaceRole(undefined); };
  const replacementChoices = useMemo(() => replaceRole ? items.filter(item => roleForItem(item) === replaceRole && !selectedOutfit?.clothingItemIds.includes(item.id)) : [], [replaceRole, items, selectedOutfit]);

  const renderWardrobe = () => <View style={s.shell}><FlatList data={items} numColumns={2} columnWrapperStyle={s.cardRow} keyExtractor={item => item.id} style={s.list} contentContainerStyle={s.listContent} ListHeaderComponent={<View><Text style={s.eyebrow}>YOUR EVERYDAY, REIMAGINED</Text><Text style={s.title}>My wardrobe</Text><Text style={s.sub}>Good style starts with what you own.</Text><TouchableOpacity accessibilityRole="button" style={s.primaryButton} onPress={() => { setUri(undefined); setResult(undefined); setLabMode(false); setScreen('review'); }}><Text style={s.primaryButtonText}>＋ Add clothing</Text></TouchableOpacity><TextInput value={search} onChangeText={setSearch} placeholder="Search color, type, style…" style={s.search} /><ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.filterRow}>{categoryFilters.map(filter => <Chip key={filter} label={filter} selected={category === filter} onPress={() => setCategory(filter)} />)}</ScrollView></View>} renderItem={({ item }) => <TouchableOpacity accessibilityRole="button" style={s.card} onPress={() => { setSelected(item); setScreen('detail'); }}><WardrobeImage imageId={item.imageId} style={s.cardImage} /><Text style={s.cardName} numberOfLines={1}>{item.name}</Text><Text style={s.cardMeta} numberOfLines={1}>{item.isFavorite ? '♥ Favorite · ' : ''}{displayValue(item.color)}</Text></TouchableOpacity>} ListEmptyComponent={<View style={s.empty}>{loading ? <Text style={s.emptyTitle}>Loading wardrobe…</Text> : wardrobeError ? <><Text style={s.emptyTitle}>Wardrobe unavailable</Text><Text style={s.errorText}>{wardrobeError}</Text><Button title="Retry" onPress={refreshWardrobe} /></> : <><View style={s.emptyIcon}><Ionicons name="shirt-outline" size={36} color={colors.accent} /></View><Text style={s.emptyTitle}>A little space for your style.</Text><Text style={s.emptyText}>Add your first clothing item to start building your digital closet.</Text><Button title="Add your first piece" onPress={() => { setUri(undefined); setResult(undefined); setLabMode(false); setScreen('review'); }} /></>}</View>}  /></View>;

  const renderReview = () => <View style={s.shell}><KeyboardAvoidingView style={s.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}><ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={s.scrollContent} keyboardDismissMode="interactive" keyboardShouldPersistTaps="handled"><Text style={s.title}>{labMode ? 'AI MODEL LAB' : 'ADD CLOTHING'}</Text>{!uri && <>{renderGuidance()}<Button title="Take Photo" onPress={() => pick(true)} /><Button title="Choose From Photos" onPress={() => pick(false)} /></>}{uri && <><Image source={{ uri }} style={s.photo} />{renderGuidance()}{!result && <Button title={busy ? stage : 'Analyze'} disabled={busy} onPress={analyze} />}{busy && <Text style={s.stage}>{stage}</Text>}{analysisError && <View style={s.errorBox}><Text style={s.errorText}>{analysisError}</Text><Button title="Try Again" onPress={analyze} /><Button title="Retake Photo" onPress={() => pick(true, labMode)} /><Button title="Cancel" onPress={() => setScreen(labMode ? 'lab' : 'wardrobe')} /></View>}{result && <><Text style={s.section}>{labMode ? 'ANALYSIS RESULT' : 'REVIEW BEFORE SAVING'}</Text>{result.qualityWarnings?.length > 0 && <View style={s.warningBox}><Text style={s.warningText}>Photo feedback: {result.qualityWarnings.join(' · ')}</Text></View>}{renderEditor()}{!labMode && <><Button title={saveBusy ? 'Saving…' : 'SAVE TO WARDROBE'} disabled={saveBusy} onPress={saveNewItem} />{saveError ? <Text style={s.errorText}>{saveError}</Text> : null}</>}{labMode && <><Text style={s.section}>Correction playground</Text>{attributes.map(attribute => <View key={attribute}><Text style={s.label}>{attribute}</Text><Text>{displayValue(result[attribute])}</Text><TextInput placeholder="Correct value (optional)" value={corrections[attribute] ?? ''} onChangeText={value => setCorrections({ ...corrections, [attribute]: value })} onEndEditing={async () => { if (corrections[attribute]) { try { await saveCorrection(result.imageId, attribute, result[attribute], corrections[attribute]); Alert.alert('Saved', 'Your correction was preserved.'); } catch (error) { Alert.alert('Correction not saved', friendlyApiError(error)); } } }} style={s.input} /></View>)}</>}{labMode && <Text selectable style={s.raw}>{result.rawResponse}</Text>}<Button title={labMode ? 'Back to AI Lab' : 'Retake Photo'} onPress={() => labMode ? setScreen('lab') : pick(true)} /></>}</>}</ScrollView></KeyboardAvoidingView></View>;

  const renderDetail = () => selected ? <View style={s.shell}><ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={s.scrollContent}><WardrobeImage imageId={selected.imageId} variant="original" style={s.detailImage} /><Text style={s.title}>{selected.name}</Text>{selected.brand ? <Text style={s.sub}>{selected.brand}</Text> : null}<Button title={selected.isFavorite ? '♥ REMOVE FROM FAVORITES' : '♡ FAVORITE THIS ITEM'} onPress={toggleFavorite} />{[['Category', selected.category], ['Type', selected.type], ['Color', selected.color], ['Pattern', selected.pattern], ['Fabric', selected.fabric], ['Fit', selected.fit], ['Style', selected.style], ['Occasions', selected.occasion], ['Seasons', selected.season]].map(([label, value]) => <View key={String(label)} style={s.detailRow}><Text style={s.detailLabel}>{label}</Text><Text>{displayValue(value)}</Text></View>)}<Text style={s.section}>AI DETAILS</Text><Text>Model: {selected.aiModelVersion}</Text><Text>Confidence: {Object.entries(selected.aiConfidence ?? {}).filter(([, value]) => value != null).map(([key, value]) => `${key} ${Math.round(Number(value) * 100)}%`).join(' · ') || 'Not provided'}</Text><Text style={s.note}>Created: {selected.createdAt}</Text>{selected.userCorrected && <Text style={s.corrected}>Includes user corrections</Text>}<Button title="BUILD AN OUTFIT AROUND THIS" onPress={() => { setAnchorItem(selected); setTestLab(false); setScreen('generate'); }} /><Button title="EDIT" onPress={() => { setDraft(draftFrom(selected)); setSaveError(''); setScreen('edit'); }} /><Button title="DELETE" color="#b42318" onPress={confirmDelete} /></ScrollView></View> : null;
  const renderEdit = () => <View style={s.shell}><KeyboardAvoidingView style={s.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}><ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={s.scrollContent} keyboardShouldPersistTaps="handled"><Text style={s.title}>EDIT CLOTHING</Text>{renderEditor()}<Button title={saveBusy ? 'Saving…' : 'SAVE CHANGES'} disabled={saveBusy} onPress={saveItemEdits} />{saveError ? <Text style={s.errorText}>{saveError}</Text> : null}<Button title="Cancel" onPress={() => setScreen('detail')} /></ScrollView></KeyboardAvoidingView></View>;
  const renderLab = () => { const installed = models.filter(model => model.status === 'installed'); const future = models.filter(model => model.status !== 'installed'); return <View style={s.shell}><ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={s.scrollContent}><Text style={s.title}>AI MODEL LAB</Text><Text style={s.section}>BACKEND CONNECTION</Text><Text selectable style={s.url}>{API_CONFIGURED ? API_URL : 'EXPO_PUBLIC_API_URL is not configured'}</Text><View style={s.statusRow}><View style={[s.dot, connection.state === 'connected' ? s.green : connection.state === 'error' ? s.red : s.gray]} /><Text>{connection.state === 'checking' ? 'Checking…' : connection.state === 'connected' ? 'Connected' : connection.state === 'error' ? 'Unable to connect' : 'Not tested'}</Text></View>{connection.detail ? <Text selectable style={s.note}>{connection.detail}</Text> : null}<Button title="Test Backend Connection" disabled={connection.state === 'checking'} onPress={testConnection} />{modelsError ? <Text style={s.errorText}>{modelsError}</Text> : null}<Text style={s.section}>INSTALLED MODELS</Text>{modelsLoading ? <Text>Loading model status…</Text> : installed.length ? installed.map(model => <Text key={model.id}>✓ {model.name} · Installed</Text>) : <Text>○ No installed model reported</Text>}<Text style={s.section}>FUTURE MODELS</Text>{modelsLoading ? <Text>Loading model status…</Text> : future.length ? future.map(model => <Text key={model.id}>○ {model.name} · Not Installed</Text>) : <Text>No future models reported</Text>}<Text style={s.note}>The outfit engine uses structured wardrobe data and never downloads another model.</Text><Button title="Open Developer Outfit Lab" onPress={() => { setTestLab(true); setAnchorItem(undefined); setScreen('outfitLab'); }} /><Button title="Select Lab Photo" onPress={() => pick(false, true)} /></ScrollView></View>; };

  const renderPersonalization = () => <View style={s.shell}><ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={s.scrollContent}><Text style={s.title}>PERSONALIZE</Text><Text style={s.sub}>Tell the wardrobe what you enjoy. These choices stay on this computer.</Text><Text style={s.section}>STYLES I LIKE</Text><View style={s.chips}>{outfitStyles.filter(value => value !== 'Any').map(value => <Chip key={`like-${value}`} label={value} selected={preferredStyles.includes(value)} onPress={() => { setPreferredStyles(current => current.includes(value) ? current.filter(item => item !== value) : [...current, value]); setDislikedStyles(current => current.filter(item => item !== value)); }} />)}</View><Text style={s.section}>STYLES I DON'T USUALLY WEAR</Text><View style={s.chips}>{outfitStyles.filter(value => value !== 'Any').map(value => <Chip key={`dislike-${value}`} label={value} selected={dislikedStyles.includes(value)} onPress={() => { setDislikedStyles(current => current.includes(value) ? current.filter(item => item !== value) : [...current, value]); setPreferredStyles(current => current.filter(item => item !== value)); }} />)}</View><TouchableOpacity accessibilityRole="button" style={s.primaryButton} onPress={savePreferences}><Text style={s.primaryButtonText}>SAVE PREFERENCES</Text></TouchableOpacity>{personalizationError ? <Text style={s.errorText}>{personalizationError}</Text> : null}<Text style={s.section}>FAVORITES</Text>{personalization?.favoriteItems?.length ? personalization.favoriteItems.map(item => <Text key={item.id} style={s.savedCard}>♥ {item.name}</Text>) : <Text style={s.note}>Favorite clothing items appear here as you mark them in your wardrobe.</Text>}<Text style={s.section}>LEARNED FROM YOUR FEEDBACK</Text><Text style={s.note}>{Object.keys(personalization?.learned?.styles ?? {}).length ? Object.entries(personalization?.learned?.styles ?? {}).map(([key, value]) => `${key}: ${Number(value) > 0 ? 'liked' : 'avoided'}`).join(' · ') : 'No learned preferences yet.'}</Text><Button title="RESET LEARNED PREFERENCES" color="#b42318" onPress={() => Alert.alert('Reset learned preferences?', 'This removes learned signals but keeps your wardrobe, favorites, saved outfits, and feedback history.', [{ text: 'Cancel', style: 'cancel' }, { text: 'Reset', style: 'destructive', onPress: async () => { try { setPersonalization(await resetLearnedPreferences()); Alert.alert('Learned preferences reset', 'Explicit style choices remain saved.'); } catch (error) { setPersonalizationError(friendlyApiError(error)); } } }])} /></ScrollView></View>;
  const renderPersonalizationLab = () => <View style={s.shell}><ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={s.scrollContent}><Text style={s.title}>DEVELOPER PERSONALIZATION LAB</Text><Text style={s.sub}>Inspect the real local signals behind recommendation changes.</Text>{personalizationError ? <Text style={s.errorText}>{personalizationError}</Text> : null}<Text style={s.section}>CURRENT EXPLICIT PREFERENCES</Text><Text selectable style={s.raw}>{JSON.stringify(personalization?.explicit ?? {}, null, 2)}</Text><Text style={s.section}>LEARNED PREFERENCES</Text><Text selectable style={s.raw}>{JSON.stringify(personalization?.learned ?? {}, null, 2)}</Text><Text style={s.section}>FAVORITE CLOTHING</Text><Text>{personalization?.favoriteItems?.map(item => item.name).join(' · ') || 'None'}</Text><Text style={s.section}>RECENT FEEDBACK</Text>{personalization?.recentFeedback?.length ? personalization.recentFeedback.slice(0, 8).map(feedback => <View key={feedback.id} style={s.savedCard}><Text style={s.outfitItemName}>{String(feedback.action).toUpperCase()}</Text><Text>{feedback.reason || 'No reason'} · {feedback.createdAt}</Text></View>) : <Text style={s.note}>No feedback recorded.</Text>}<Text style={s.section}>RECENT HISTORY</Text><Text>{personalization?.recentHistory?.slice(0, 8).map(entry => `${entry.eventType}: ${Number(entry.personalizedScore ?? 0).toFixed(1)}`).join(' · ') || 'No outfit history recorded.'}</Text>{outfitResult?.score && <><Text style={s.section}>CURRENT GENERATION</Text><Text>Base Score: {outfitResult.score.baseTotal ?? outfitResult.score.total}</Text><Text>Personalization Bonus: {(outfitResult.score.personalizationBonus ?? 0) >= 0 ? '+' : ''}{outfitResult.score.personalizationBonus ?? 0}</Text><Text style={s.scoreTotal}>Final Score: {outfitResult.score.total}</Text><Text style={s.note}>{outfitResult.score.reasons?.join(' · ') || 'No preference adjustments in this run.'}</Text></>}<Button title="Refresh Lab" onPress={() => refreshPersonalization(true)} /></ScrollView></View>;
  const renderOutfitConfig = () => <View style={s.shell}><ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={s.scrollContent}><Text style={s.title}>{testLab ? 'OUTFIT ENGINE LAB' : 'GET DRESSED'}</Text><Text style={s.sub}>{anchorItem ? `Building around ${anchorItem.name}` : 'Choose a few preferences. The engine uses only saved wardrobe items.'}</Text><Text style={s.fieldLabel}>Occasion</Text><View style={s.chips}>{outfitOccasions.map(value => <Chip key={value} label={value} selected={outfitOccasion === value} onPress={() => setOutfitOccasion(value)} />)}</View><Text style={s.fieldLabel}>Style</Text><View style={s.chips}>{outfitStyles.map(value => <Chip key={value} label={value} selected={outfitStyle === value} onPress={() => setOutfitStyle(value)} />)}</View><Text style={s.fieldLabel}>Season</Text><View style={s.chips}>{outfitSeasons.map(value => <Chip key={value} label={value} selected={outfitSeason === value} onPress={() => setOutfitSeason(value)} />)}</View>{!testLab && <><Text style={s.fieldLabel}>Build around a specific item</Text><ScrollView horizontal showsHorizontalScrollIndicator={false}><Chip label="Any item" selected={!anchorItem} onPress={() => setAnchorItem(undefined)} />{items.map(item => <Chip key={item.id} label={item.name} selected={anchorItem?.id === item.id} onPress={() => setAnchorItem(item)} />)}</ScrollView></>}<TouchableOpacity accessibilityRole="button" style={s.primaryButton} onPress={() => runGeneration(false)} disabled={outfitLoading}><Text style={s.primaryButtonText}>{outfitLoading ? 'BUILDING…' : 'GENERATE OUTFIT'}</Text></TouchableOpacity><Button title={testLab ? 'Back to AI Lab' : 'Back to Outfits'} onPress={() => setScreen(testLab ? 'lab' : 'outfits')} /></ScrollView></View>;
  const renderScore = (generation: OutfitGeneration) => generation.score ? <View style={s.scoreBox}><Text style={s.section}>WHY THIS OUTFIT</Text><Text style={s.scoreTotal}>{generation.score.total}/100</Text>{Object.entries(generation.score.components).map(([key, value]) => <View key={key} style={s.scoreRow}><Text style={s.scoreLabel}>{key}</Text><Text>{value}/10</Text></View>)}{generation.score.reasons?.length ? <Text style={s.note}>Notes: {generation.score.reasons.join(' · ')}</Text> : null}</View> : null;
  const renderResult = () => { if (!outfitResult) return null; return <View style={s.shell}><ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={s.scrollContent}><Text style={s.title}>{outfitResultSource === 'test' ? 'TEST OUTFIT' : 'YOUR OUTFIT'}</Text><Text style={s.sub}>{outfitResultSource === 'test' ? 'Fictional lab preview — not part of your wardrobe' : outfitResult.isComplete ? 'A complete look from your wardrobe' : 'Best available from your wardrobe'}</Text>{outfitResult.items.map(item => <OutfitItemCard key={item.id} item={item} onReplace={outfitResultSource === 'test' ? undefined : () => setReplaceRole(roleForItem(item))} />)}{outfitResult.missingRoles?.length ? <View style={s.warningBox}><Text style={s.warningText}>Missing: {outfitResult.missingRoles.join(' · ')}</Text><Text>Add more items to complete this outfit.</Text></View> : null}<Text style={s.explanation}>{outfitResult.explanation}</Text><Text style={s.metaLine}>Occasion: {outfitOccasion} · Style: {outfitStyle} · Season: {outfitSeason}</Text>{renderScore(outfitResult)}{replaceRole && outfitResultSource !== 'test' && <View style={s.replaceBox}><Text style={s.section}>REPLACE {replaceRole.toUpperCase()}</Text>{items.filter(item => roleForItem(item) === replaceRole && !outfitResult.clothingItemIds.includes(item.id)).map(item => <TouchableOpacity key={item.id} style={s.replaceChoice} onPress={() => updateGeneratedItem(replaceRole, item)}><Text style={s.outfitItemName}>{item.name}</Text><Text>{displayValue(item.color)} · {displayValue(item.style)}</Text></TouchableOpacity>)}<Button title="Cancel" onPress={() => setReplaceRole(undefined)} /></View>}{outfitResultSource !== 'test' && <><Text style={s.section}>HOW DID THIS FEEL?</Text><View style={s.chips}><Chip label="♥ Like" selected={false} onPress={() => feedbackFor('like')} /><Chip label="Not for me" selected={false} onPress={() => feedbackFor('dislike')} /></View></>}<TouchableOpacity accessibilityRole="button" style={s.primaryButton} onPress={() => runGeneration(true, outfitResultSource)} disabled={outfitLoading}><Text style={s.primaryButtonText}>{outfitLoading ? 'REGENERATING…' : '↻ REGENERATE'}</Text></TouchableOpacity>{outfitResultSource !== 'test' && outfitResult.available && <Button title={saveBusy ? 'Saving…' : '♥ SAVE OUTFIT'} disabled={saveBusy} onPress={saveGeneratedOutfit} />}{outfitResultSource === 'test' && <Text style={s.note}>Test wardrobe data is fictional and cannot be saved into your real wardrobe.</Text>}</ScrollView></View>; };
  const renderOutfits = () => <View style={s.shell}><ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={s.scrollContent}><Text style={s.title}>OUTFITS</Text><Text style={s.sub}>Looks made from pieces you already own.</Text><TouchableOpacity accessibilityRole="button" style={s.primaryButton} onPress={() => { setTestLab(false); setAnchorItem(undefined); setScreen('generate'); }}><Text style={s.primaryButtonText}>＋ GENERATE OUTFIT</Text></TouchableOpacity>{outfitResult && <><Text style={s.section}>RECENTLY GENERATED</Text><TouchableOpacity accessibilityRole="button" style={s.recentCard} onPress={() => setScreen('result')}><Text style={s.outfitItemName}>{outfitResult.items.map(item => item.name).join(' · ') || 'No complete outfit yet'}</Text><Text>{outfitResult.score?.total ?? 0}/100 · Tap to view</Text></TouchableOpacity></>}{outfitsError ? <View style={s.errorBox}><Text style={s.errorText}>{outfitsError}</Text><Button title="Retry" onPress={refreshOutfits} /></View> : null}<Text style={s.section}>SAVED OUTFITS</Text>{outfitLoading ? <Text>Loading saved outfits…</Text> : outfits.length ? outfits.map(outfit => <TouchableOpacity key={outfit.id} style={s.savedCard} onPress={async () => { try { setSelectedOutfit(await getOutfit(outfit.id)); setScreen('outfitDetail'); } catch (error) { Alert.alert('Could not open outfit', friendlyApiError(error)); } }}><Text style={s.outfitItemName}>{outfit.name}</Text><Text>{outfit.clothingItems.map(item => item.name).join(' · ') || 'Some items unavailable'}</Text>{outfit.deletedItemIds.length ? <Text style={s.errorText}>{outfit.deletedItemIds.length} deleted item(s) need replacing</Text> : null}{outfit.userRating ? <Text>Rating: {outfit.userRating}/5</Text> : null}</TouchableOpacity>) : <Text style={s.emptyText}>No saved outfits yet. Generate one when you are ready.</Text>}</ScrollView></View>;
  const renderOutfitDetail = () => selectedOutfit ? <View style={s.shell}><ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={s.scrollContent}><Text style={s.title}>{selectedOutfit.name}</Text><Text style={s.sub}>{selectedOutfit.occasion ?? 'Any occasion'} · {selectedOutfit.style ?? 'Any style'} · {selectedOutfit.season ?? 'Any season'}</Text>{selectedOutfit.clothingItems.map(item => <OutfitItemCard key={item.id} item={item} onReplace={() => setReplaceRole(roleForItem(item))} />)}{selectedOutfit.deletedItemIds.map(id => { const role = selectedOutfit.deletedItemRoles[id]; return <View key={id} style={s.warningBox}><Text style={s.warningText}>A saved item is no longer in the wardrobe.</Text><Text selectable>Missing item ID: {id}</Text>{role ? <Button title={`Replace missing ${role}`} onPress={() => setReplaceRole(role)} /> : <Text style={s.note}>The original role is unavailable; add a matching item and edit the outfit from the API later.</Text>}</View>; })}{replaceRole && <View style={s.replaceBox}><Text style={s.section}>REPLACE {replaceRole.toUpperCase()}</Text>{replacementChoices.map(item => <TouchableOpacity key={item.id} style={s.replaceChoice} onPress={async () => { try { setSelectedOutfit(await replaceOutfitItem(selectedOutfit.id, replaceRole, item.id)); setReplaceRole(undefined); } catch (error) { Alert.alert('Could not replace item', friendlyApiError(error)); } }}><Text style={s.outfitItemName}>{item.name}</Text><Text>{displayValue(item.color)} · {displayValue(item.style)}</Text></TouchableOpacity>)}<Button title="Cancel" onPress={() => setReplaceRole(undefined)} /></View>}<Text style={s.explanation}>{selectedOutfit.generationMetadata?.explanation ?? 'Saved from your wardrobe.'}</Text><Text style={s.section}>RATE THIS OUTFIT</Text><View style={s.chips}>{[1, 2, 3, 4, 5].map(value => <Chip key={value} label={`${value} ★`} selected={selectedOutfit.userRating === value} onPress={async () => { try { setSelectedOutfit(await rateOutfit(selectedOutfit.id, value)); } catch (error) { Alert.alert('Could not save rating', friendlyApiError(error)); } }} />)}</View><Text style={s.section}>FEEDBACK</Text><View style={s.chips}><Chip label="♥ Like" selected={false} onPress={() => feedbackFor('like', selectedOutfit.id)} /><Chip label="Not for me" selected={false} onPress={() => feedbackFor('dislike', selectedOutfit.id)} /></View><Button title="WORE THIS" onPress={async () => { try { await markOutfitWorn(selectedOutfit.id); Alert.alert('Recorded', 'This outfit was added to your worn history.'); } catch (error) { Alert.alert('Could not record outfit', friendlyApiError(error)); } }} /></ScrollView></View> : null;
  const renderOutfitLab = () => <View style={s.shell}><ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={s.scrollContent}><Text style={s.title}>DEVELOPER OUTFIT LAB</Text><Text style={s.sub}>Deterministic fixture data for tuning compatibility and ranking. It never enters your real wardrobe.</Text><Text style={s.section}>TEST SCENARIO</Text><View style={s.chips}>{['Everyday', 'Formal', 'Summer', 'Winter'].map(value => <Chip key={value} label={value} selected={outfitOccasion === value || outfitSeason === value} onPress={() => { if (outfitSeasons.includes(value)) setOutfitSeason(value); else setOutfitOccasion(value); }} />)}</View><Button title="Generate Fixture Outfit" onPress={() => runGeneration(false, 'test', 'outfitLab')} />{outfitResult && <>{outfitResult.items.map(item => <OutfitItemCard key={item.id} item={item} />)}{renderScore(outfitResult)}<Text style={s.section}>REJECTED CANDIDATES</Text>{outfitResult.rejected?.length ? outfitResult.rejected.map(candidate => <View key={candidate.clothingItemId} style={s.rejected}><Text style={s.outfitItemName}>{candidate.name}</Text><Text>{candidate.reasons.join(' · ')}</Text></View>) : <Text>No rejected candidate reasons in this run.</Text>}<Text style={s.note}>Candidates: {outfitResult.candidates?.length ?? 0}. Generated from structured attributes; no additional AI inference.</Text></>}</ScrollView></View>;

const renderProfile = () => <View style={s.shell}>
    <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={s.scrollContent}>
      <Text style={s.eyebrow}>MADE PERSONAL</Text>
      <Text style={s.title}>Your profile</Text>
      <Text style={s.sub}>A wardrobe that feels like you.</Text>
      <View style={s.profileCard}>
        <View style={s.avatar}><Ionicons name="person-outline" size={30} color={colors.accent} /></View>
        <View style={s.rowBody}><Text style={s.profileHeading}>Make it yours</Text><Text style={s.note}>Your style, your favorites, your everyday.</Text></View>
      </View>
      <MenuRow icon="sparkles-outline" title="Style preferences" subtitle="Shape your outfit recommendations" onPress={() => setScreen('personalization')} />
      {personalizationError ? <Text style={s.errorText}>{personalizationError}</Text> : personalization ? <View style={s.profileSummary}>
        <Text style={s.detailLabel}>YOUR STYLE NOTES</Text>
        <Text>{personalization.explicit?.preferredStyles?.length ? personalization.explicit.preferredStyles.join(' · ') : 'Add the styles you love to get started.'}</Text>
        <Text style={s.note}>{personalization.favoriteItems?.length ?? 0} favorite pieces</Text>
      </View> : <Text style={s.note}>Loading your style notes…</Text>}
      <ThemePicker />
    </ScrollView>
  </View>;
  const renderSettings = () => <View style={s.shell}>
    <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={s.scrollContent}>
      <Text style={s.eyebrow}>THE LITTLE DETAILS</Text>
      <Text style={s.title}>Settings</Text>
      <Text style={s.sub}>Set the mood. Make yourself at home.</Text>
      <ThemePicker />
      <Text style={s.section}>Personalization</Text>
      <MenuRow icon="options-outline" title="Style preferences" subtitle="The styles you love and the ones you skip" onPress={() => setScreen('personalization')} />
      <Text style={s.section}>Development tools</Text>
      <Text style={s.note}>Tools for testing this local prototype.</Text>
      <MenuRow icon="flask-outline" title="AI lab" subtitle="Connection, model and photo tests" onPress={() => setScreen('lab')} />
      <MenuRow icon="layers-outline" title="Outfit lab" subtitle="Test outfit combinations with fixtures" onPress={() => { setTestLab(true); setAnchorItem(undefined); setScreen('outfitLab'); }} />
      <MenuRow icon="analytics-outline" title="Personalization lab" subtitle="Inspect your recommendation signals" onPress={() => setScreen('personalizationLab')} />
    </ScrollView>
  </View>;

  const screens: Record<Screen, () => React.ReactNode> = {
    wardrobe: renderWardrobe, detail: renderDetail, edit: renderEdit, lab: renderLab,
    outfits: renderOutfits, generate: renderOutfitConfig, result: renderResult,
    outfitDetail: renderOutfitDetail, outfitLab: renderOutfitLab, personalization: renderPersonalization,
    personalizationLab: renderPersonalizationLab, review: renderReview, profile: renderProfile, settings: renderSettings,
  };
  if (!ready) return <View style={s.shell} />;
  return <AppChrome activeTab={activeTab} canGoBack={navigation.length > 1} onBack={goBack}
    onSettings={() => setScreen('settings')} onTab={switchTab} settingsOpen={screen === 'settings'}>
    <View key={screen} style={s.flex}>{screens[screen]()}</View>
  </AppChrome>;
}

function MenuRow({ icon, title, subtitle, onPress }: {
  icon: React.ComponentProps<typeof Ionicons>['name']; title: string; subtitle: string; onPress: () => void;
}) {
  const s = useStyles();
  const { theme: { colors } } = useTheme();
  return <TouchableOpacity accessibilityRole="button" accessibilityLabel={title} onPress={onPress} style={s.menuRow}>
    <View style={s.menuIcon}><Ionicons name={icon} size={22} color={colors.accent} /></View>
    <View style={s.rowBody}><Text style={s.menuTitle}>{title}</Text><Text style={s.menuSubtitle}>{subtitle}</Text></View>
    <Ionicons name="chevron-forward" size={19} color={colors.muted} />
  </TouchableOpacity>;
}

export default function App() {
  return <SafeAreaProvider><ThemeProvider><WardrobeApp /></ThemeProvider></SafeAreaProvider>;
}

function useStyles() {
  const { theme: { colors } } = useTheme();
  return useMemo(() => createStyles(colors), [colors]);
}

const createStyles = (c: Palette) => StyleSheet.create({
  shell: { flex: 1, backgroundColor: c.background }, flex: { flex: 1 }, list: { flex: 1 },
  listContent: { padding: 20, paddingTop: 28, paddingBottom: 28 }, scrollContent: { padding: 20, paddingTop: 28, paddingBottom: 28 },
  eyebrow: { fontSize: 10, lineHeight: 16, fontWeight: '700', letterSpacing: 1.7, color: c.accent, marginBottom: 8 },
  title: { fontSize: 30, lineHeight: 38, fontWeight: '700', letterSpacing: -0.8, marginBottom: 6, color: c.text },
  sub: { marginBottom: 24, color: c.muted, fontSize: 14, lineHeight: 22 },
  section: { fontSize: 18, lineHeight: 25, fontWeight: '700', marginTop: 24, marginBottom: 12, color: c.text },
  primaryButton: { backgroundColor: c.accent, borderRadius: 16, minHeight: 52, padding: 15, alignItems: 'center', justifyContent: 'center', marginBottom: 16 },
  primaryButtonText: { color: c.onAccent, fontWeight: '700', fontSize: 15 },
  secondaryButton: { backgroundColor: c.elevated, borderRadius: 16, minHeight: 48, padding: 14, alignItems: 'center', marginBottom: 16 },
  secondaryButtonText: { color: c.text, fontWeight: '700' },
  search: { color: c.text, backgroundColor: c.surface, borderWidth: 1, borderColor: c.border, borderRadius: 14, padding: 14, marginBottom: 14 },
  filterRow: { paddingBottom: 16 }, chip: { minHeight: 44, justifyContent: 'center', borderWidth: 1, borderColor: c.border, borderRadius: 22, paddingHorizontal: 14, paddingVertical: 10, marginRight: 8, marginBottom: 8, backgroundColor: c.surface },
  chipSelected: { backgroundColor: c.accentSoft, borderColor: c.accent }, chipText: { color: c.muted, fontSize: 13 }, chipTextSelected: { color: c.accent, fontSize: 13, fontWeight: '700' },
  cardRow: { justifyContent: 'space-between' }, card: { width: '48%', backgroundColor: c.surface, borderWidth: 1, borderColor: c.border, borderRadius: 18, marginBottom: 14, overflow: 'hidden' },
  cardImage: { width: '100%', aspectRatio: 0.85, backgroundColor: c.elevated, resizeMode: 'cover' },
  imageFallback: { alignItems: 'center', justifyContent: 'center' }, imageFallbackText: { color: c.muted, fontSize: 12 },
  cardName: { fontWeight: '700', paddingHorizontal: 12, paddingTop: 11, color: c.text },
  cardMeta: { color: c.muted, paddingHorizontal: 12, paddingBottom: 12, paddingTop: 4 },
  empty: { alignItems: 'center', padding: 24, marginTop: 8, backgroundColor: c.surface, borderRadius: 24, borderWidth: 1, borderColor: c.border },
  emptyIcon: { width: 76, height: 76, borderRadius: 26, backgroundColor: c.accentSoft, alignItems: 'center', justifyContent: 'center', marginBottom: 22, marginTop: 10 },
  emptyTitle: { fontSize: 21, lineHeight: 28, fontWeight: '700', textAlign: 'center', marginBottom: 10 },
  emptyText: { color: c.muted, lineHeight: 22, textAlign: 'center', marginBottom: 18 },
  link: { color: c.accent, textAlign: 'center', marginTop: 18, padding: 12 },
  guidance: { backgroundColor: c.elevated, borderRadius: 16, padding: 16, marginVertical: 16 }, guidanceTitle: { fontWeight: '700', marginBottom: 6 },
  photo: { width: '100%', height: 300, resizeMode: 'contain', marginBottom: 12, backgroundColor: c.elevated, borderRadius: 20 },
  detailImage: { width: '100%', height: 380, resizeMode: 'contain', backgroundColor: c.elevated, marginBottom: 18, borderRadius: 20 },
  fieldLabel: { fontWeight: '700', textTransform: 'capitalize', marginTop: 16, marginBottom: 7 },
  input: { color: c.text, borderWidth: 1, borderColor: c.border, backgroundColor: c.surface, padding: 12, marginBottom: 5, borderRadius: 12 },
  chips: { flexDirection: 'row', flexWrap: 'wrap' }, stage: { color: c.accent, marginVertical: 14, textAlign: 'center' },
  errorBox: { backgroundColor: c.dangerSoft, borderRadius: 14, padding: 14, marginVertical: 14 }, errorText: { color: c.danger, marginVertical: 8 },
  warningBox: { backgroundColor: c.warningSoft, borderRadius: 14, padding: 14, marginBottom: 10 }, warningText: { color: c.warning },
  label: { fontWeight: '700', textTransform: 'capitalize', marginTop: 14 }, raw: { backgroundColor: c.elevated, padding: 12, borderRadius: 12, marginVertical: 14 },
  detailRow: { borderBottomWidth: 1, borderBottomColor: c.border, paddingVertical: 12 }, detailLabel: { color: c.muted, fontSize: 11, letterSpacing: 1, textTransform: 'uppercase', marginBottom: 5 },
  corrected: { color: c.success, marginVertical: 10 }, note: { color: c.muted, marginVertical: 10 },
  url: { fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace', fontSize: 13, marginBottom: 12, flexShrink: 1 },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 }, dot: { width: 10, height: 10, borderRadius: 5 },
  green: { backgroundColor: c.success }, red: { backgroundColor: c.danger }, gray: { backgroundColor: c.muted },
  outfitItemCard: { backgroundColor: c.surface, borderRadius: 18, borderWidth: 1, borderColor: c.border, overflow: 'hidden', marginBottom: 16 },
  outfitImage: { width: '100%', height: 220, backgroundColor: c.elevated, resizeMode: 'cover' }, outfitItemText: { padding: 14 },
  itemRole: { color: c.muted, fontSize: 11, fontWeight: '700', letterSpacing: 1 },
  outfitItemName: { color: c.text, fontWeight: '700', fontSize: 17, lineHeight: 24, marginVertical: 4 },
  explanation: { color: c.text, fontSize: 16, lineHeight: 24, backgroundColor: c.elevated, padding: 16, borderRadius: 16, marginVertical: 12 },
  metaLine: { color: c.muted, marginVertical: 8 },
  scoreBox: { backgroundColor: c.surface, borderRadius: 16, padding: 16, marginVertical: 12 }, scoreTotal: { fontSize: 28, lineHeight: 36, fontWeight: '700', color: c.accent, marginBottom: 8 },
  scoreRow: { flexDirection: 'row', justifyContent: 'space-between', borderBottomWidth: 1, borderBottomColor: c.border, paddingVertical: 8 }, scoreLabel: { textTransform: 'capitalize' },
  replaceBox: { backgroundColor: c.elevated, borderRadius: 16, padding: 14, marginVertical: 12 }, replaceChoice: { backgroundColor: c.surface, borderRadius: 12, padding: 14, marginBottom: 8 },
  savedCard: { backgroundColor: c.surface, borderWidth: 1, borderColor: c.border, borderRadius: 16, padding: 16, marginBottom: 12 },
  recentCard: { backgroundColor: c.accentSoft, borderRadius: 16, padding: 16, marginBottom: 12 }, rejected: { backgroundColor: c.dangerSoft, borderRadius: 14, padding: 14, marginBottom: 8 },
  profileCard: { flexDirection: 'row', alignItems: 'center', gap: 16, backgroundColor: c.accentSoft, borderRadius: 24, padding: 20, marginBottom: 20 },
  avatar: { width: 64, height: 64, borderRadius: 23, alignItems: 'center', justifyContent: 'center', backgroundColor: c.surface },
  profileHeading: { fontSize: 20, lineHeight: 27, fontWeight: '700' }, rowBody: { flex: 1, minWidth: 0 },
  profileSummary: { padding: 16, marginBottom: 6 }, menuRow: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 80, padding: 14, borderRadius: 18, borderWidth: 1, borderColor: c.border, backgroundColor: c.surface, marginBottom: 10 },
  menuIcon: { width: 42, height: 42, borderRadius: 14, backgroundColor: c.accentSoft, alignItems: 'center', justifyContent: 'center' },
  menuTitle: { fontWeight: '700', fontSize: 15 }, menuSubtitle: { color: c.muted, fontSize: 12, lineHeight: 18, marginTop: 3 },
});
