import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Button, FlatList, Image, KeyboardAvoidingView, Platform, SafeAreaView, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { API_CONFIGURED, API_URL, ClothingItem, analyzePhoto, deleteWardrobeItem, friendlyApiError, getHealth, getModels, getWardrobe, imageUrl, saveCorrection, saveWardrobeItem, updateWardrobeItem } from './src/api';

const attributes = ['category', 'type', 'color', 'pattern', 'fabric', 'fit', 'style', 'occasion', 'season'];
const categoryFilters = ['All', 'Tops', 'Bottoms', 'Shoes', 'Outerwear', 'Accessories'];
const categoryChoices = ['Top', 'Bottom', 'Shoes', 'Outerwear', 'Accessories'];
const colorChoices = ['Black', 'White', 'Navy', 'Blue', 'Brown', 'Gray', 'Green', 'Red', 'Beige'];
const patternChoices = ['Solid', 'Striped', 'Plaid', 'Graphic', 'Floral', 'Printed'];
const fabricChoices = ['Cotton', 'Denim', 'Wool', 'Leather', 'Linen', 'Synthetic', 'Knit'];
const fitChoices = ['Slim', 'Regular', 'Relaxed', 'Oversized'];
const styleChoices = ['Casual', 'Smart casual', 'Formal', 'Sporty', 'Minimal', 'Vintage', 'Streetwear'];
const occasionChoices = ['Everyday', 'Work', 'Formal', 'Travel', 'Workout', 'Outdoor'];
const seasonChoices = ['Spring', 'Summer', 'Fall', 'Winter', 'All season'];

type Screen = 'wardrobe' | 'review' | 'detail' | 'edit' | 'lab';
type Draft = Record<string, any>;
type Connection = { state: 'idle' | 'checking' | 'connected' | 'error'; detail?: string };

const arrayOrEmpty = (value: any) => Array.isArray(value) ? value : value ? [value] : [];
const draftFrom = (value: any): Draft => ({
  name: value?.name ?? '', brand: value?.brand ?? '', category: value?.category ?? '', type: value?.type ?? '', color: value?.color ?? '',
  secondaryColors: arrayOrEmpty(value?.secondaryColors), pattern: value?.pattern ?? '', fabric: value?.fabric ?? '', fit: value?.fit ?? '',
  style: arrayOrEmpty(value?.style), occasion: arrayOrEmpty(value?.occasion ?? value?.occasions), season: arrayOrEmpty(value?.season ?? value?.seasons),
});
const displayValue = (value: any) => Array.isArray(value) ? value.join(' · ') || 'Not detected' : value || 'Not detected';

function Chip({ label, selected, onPress }: { label: string; selected: boolean; onPress: () => void }) {
  return <TouchableOpacity onPress={onPress} style={[s.chip, selected && s.chipSelected]}><Text style={selected ? s.chipTextSelected : s.chipText}>{label}</Text></TouchableOpacity>;
}

function WardrobeImage({ imageId, variant = 'thumbnail', style }: { imageId: string; variant?: 'thumbnail' | 'original'; style: any }) {
  const [failed, setFailed] = useState(false);
  return failed
    ? <View style={[style, s.imageFallback]}><Text style={s.imageFallbackText}>Photo unavailable</Text></View>
    : <Image source={{ uri: imageUrl(imageId, variant) }} style={style} onError={() => setFailed(true)} />;
}

export default function App() {
  const [screen, setScreen] = useState<Screen>('wardrobe');
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

  const refreshWardrobe = async () => {
    setLoading(true);
    try { setItems(await getWardrobe(search, category)); setWardrobeError(''); }
    catch (error) { setWardrobeError(friendlyApiError(error)); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    if (screen !== 'wardrobe' || !API_CONFIGURED) return;
    const timer = setTimeout(refreshWardrobe, 250);
    return () => clearTimeout(timer);
  }, [screen, search, category]);

  useEffect(() => {
    if (screen !== 'lab' || !API_CONFIGURED) return;
    setModelsLoading(true); setModelsError('');
    getModels().then(setModels).catch(error => { setModelsError(friendlyApiError(error)); }).finally(() => setModelsLoading(false));
  }, [screen]);

  const pick = async (camera = false, fromLab = false) => {
    const permission = camera ? await ImagePicker.requestCameraPermissionsAsync() : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) return Alert.alert('Permission needed', 'Allow photo access in iPhone Settings.');
    const selection = camera
      ? await ImagePicker.launchCameraAsync({ mediaTypes: ['images'], quality: 0.9 })
      : await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.9 });
    if (!selection.canceled) {
      setUri(selection.assets[0].uri); setResult(undefined); setDraft({}); setAnalysisError(''); setSaveError(''); setLabMode(fromLab); setScreen('review');
    }
  };

  const analyze = async () => {
    if (!uri) return;
    setBusy(true); setAnalysisError(''); setStage('Uploading photo…');
    try {
      setStage('Analyzing your clothing locally…');
      const analysis = await analyzePhoto(uri);
      setResult(analysis); setDraft(draftFrom(analysis)); setStage('');
    } catch (error) { setAnalysisError(friendlyApiError(error)); setStage(''); }
    finally { setBusy(false); }
  };

  const testConnection = async () => {
    setConnection({ state: 'checking' });
    try {
      const health = await getHealth();
      setConnection({ state: 'connected', detail: `${health.modelName} · ${health.modelCached ? 'Model cached locally' : 'Model cache not found'}` });
    } catch (error) { setConnection({ state: 'error', detail: friendlyApiError(error) }); }
  };

  const saveNewItem = async () => {
    if (!result || saveBusy) return;
    setSaveBusy(true); setSaveError('');
    try {
      await saveWardrobeItem({ ...draft, imageId: result.imageId, modelId: result.modelId, modelVersion: result.modelVersion, confidence: result.confidence, rawResponse: result.rawResponse, inferenceTimeMs: result.inferenceTimeMs, parseSuccess: result.parseSuccess });
      setScreen('wardrobe'); Alert.alert('Added to wardrobe.', 'Your clothing item is ready to browse.'); refreshWardrobe().catch(() => undefined);
    } catch (error) { setSaveError(friendlyApiError(error)); }
    finally { setSaveBusy(false); }
  };

  const saveItemEdits = async () => {
    if (!selected || saveBusy) return;
    setSaveBusy(true); setSaveError('');
    try { const updated = await updateWardrobeItem(selected.id, draft); setSelected(updated); setScreen('detail'); refreshWardrobe().catch(() => undefined); }
    catch (error) { setSaveError(friendlyApiError(error)); }
    finally { setSaveBusy(false); }
  };

  const confirmDelete = () => {
    if (!selected) return;
    Alert.alert('Delete clothing item?', 'The saved wardrobe record will be removed. Your original image and analysis history will remain available.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => { try { await deleteWardrobeItem(selected.id); setItems(current => current.filter(item => item.id !== selected.id)); setSelected(undefined); setScreen('wardrobe'); refreshWardrobe().catch(() => undefined); } catch (error) { Alert.alert('Delete failed', friendlyApiError(error)); } } },
    ]);
  };

  const updateDraft = (key: string, value: any) => setDraft((current) => ({ ...current, [key]: value }));
  const toggleDraftArray = (key: string, value: string) => updateDraft(key, arrayOrEmpty(draft[key]).includes(value) ? arrayOrEmpty(draft[key]).filter((item: string) => item !== value) : [...arrayOrEmpty(draft[key]), value]);

  const renderChoice = (label: string, key: string, choices: string[]) => <View><Text style={s.fieldLabel}>{label}</Text><View style={s.chips}>{choices.map(choice => <Chip key={choice} label={choice} selected={draft[key] === choice} onPress={() => updateDraft(key, choice)} />)}</View><TextInput value={draft[key] ?? ''} onChangeText={value => updateDraft(key, value)} placeholder={`Enter ${label.toLowerCase()} if needed`} style={s.input} /></View>;
  const renderMultiChoice = (label: string, key: string, choices: string[]) => <View><Text style={s.fieldLabel}>{label}</Text><View style={s.chips}>{choices.map(choice => <Chip key={choice} label={choice} selected={arrayOrEmpty(draft[key]).includes(choice)} onPress={() => toggleDraftArray(key, choice)} />)}</View></View>;

  const renderEditor = () => <View>
    <Text style={s.fieldLabel}>Name</Text><TextInput value={draft.name ?? ''} onChangeText={value => updateDraft('name', value)} placeholder="e.g. Navy Polo" style={s.input} />
    <Text style={s.fieldLabel}>Brand (optional)</Text><TextInput value={draft.brand ?? ''} onChangeText={value => updateDraft('brand', value)} placeholder="Add manually if known" style={s.input} />
    {renderChoice('Category', 'category', categoryChoices)}
    <Text style={s.fieldLabel}>Type</Text><TextInput value={draft.type ?? ''} onChangeText={value => updateDraft('type', value)} placeholder="e.g. polo, jeans, boots" style={s.input} />
    {renderChoice('Color', 'color', colorChoices)}
    {renderChoice('Pattern', 'pattern', patternChoices)}
    {renderChoice('Fabric', 'fabric', fabricChoices)}
    {renderChoice('Fit', 'fit', fitChoices)}
    {renderMultiChoice('Style', 'style', styleChoices)}
    {renderMultiChoice('Occasions', 'occasion', occasionChoices)}
    {renderMultiChoice('Seasons', 'season', seasonChoices)}
  </View>;

  const renderGuidance = () => <View style={s.guidance}><Text style={s.guidanceTitle}>Photo tips</Text><Text>• Lay the item flat or hang it up.</Text><Text>• Make sure the entire item is visible.</Text><Text>• Use good lighting and avoid other clothing in frame.</Text></View>;

  const renderWardrobe = () => <SafeAreaView style={s.shell}><FlatList
    data={items} numColumns={2} keyExtractor={item => item.id} style={s.list} contentContainerStyle={s.listContent}
    ListHeaderComponent={<View><Text style={s.title}>MY WARDROBE</Text><Text style={s.sub}>Your digital closet</Text><TouchableOpacity style={s.primaryButton} onPress={() => { setUri(undefined); setResult(undefined); setLabMode(false); setScreen('review'); }}><Text style={s.primaryButtonText}>＋ ADD CLOTHING</Text></TouchableOpacity><TextInput value={search} onChangeText={setSearch} placeholder="Search color, type, style…" style={s.search} /><ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.filterRow}>{categoryFilters.map(filter => <Chip key={filter} label={filter} selected={category === filter} onPress={() => setCategory(filter)} />)}</ScrollView></View>}
    renderItem={({ item }) => <TouchableOpacity style={s.card} onPress={() => { setSelected(item); setScreen('detail'); }}><WardrobeImage imageId={item.imageId} style={s.cardImage} /><Text style={s.cardName} numberOfLines={1}>{item.name}</Text><Text style={s.cardMeta} numberOfLines={1}>{displayValue(item.color)}</Text></TouchableOpacity>}
    ListEmptyComponent={<View style={s.empty}>{loading ? <Text style={s.emptyTitle}>Loading wardrobe…</Text> : wardrobeError ? <><Text style={s.emptyTitle}>Wardrobe unavailable</Text><Text style={s.errorText}>{wardrobeError}</Text><Button title="Retry" onPress={refreshWardrobe} /></> : <><Text style={s.emptyTitle}>Your wardrobe is empty.</Text><Text style={s.emptyText}>Add your first clothing item to start building your digital closet.</Text><Button title="Add First Clothing Item" onPress={() => setScreen('review')} /></>}</View>}
    ListFooterComponent={<TouchableOpacity onPress={() => setScreen('lab')}><Text style={s.link}>Developer AI Lab</Text></TouchableOpacity>}
  /></SafeAreaView>;

  const renderReview = () => <SafeAreaView style={s.shell}><KeyboardAvoidingView style={s.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}><ScrollView contentContainerStyle={s.scrollContent} keyboardDismissMode="interactive" keyboardShouldPersistTaps="handled"><Text style={s.title}>{labMode ? 'AI MODEL LAB' : 'ADD CLOTHING'}</Text>{!uri && <>{renderGuidance()}<Button title="Take Photo" onPress={() => pick(true)} /><Button title="Choose From Photos" onPress={() => pick(false)} /><Button title="Back to Wardrobe" onPress={() => setScreen('wardrobe')} /></>}{uri && <><Image source={{ uri }} style={s.photo} />{renderGuidance()}{!result && <Button title={busy ? stage : 'Analyze'} disabled={busy} onPress={analyze} />}{busy && <Text style={s.stage}>{stage}</Text>}{analysisError && <View style={s.errorBox}><Text style={s.errorText}>{analysisError}</Text><Button title="Try Again" onPress={analyze} /><Button title="Retake Photo" onPress={() => pick(true, labMode)} /><Button title="Cancel" onPress={() => setScreen(labMode ? 'lab' : 'wardrobe')} /></View>}{result && <><Text style={s.section}>{labMode ? 'ANALYSIS RESULT' : 'REVIEW BEFORE SAVING'}</Text>{result.qualityWarnings?.length > 0 && <View style={s.warningBox}><Text style={s.warningText}>Photo feedback: {result.qualityWarnings.join(' · ')}</Text></View>}{renderEditor()}{!labMode && <><Button title={saveBusy ? 'Saving…' : 'SAVE TO WARDROBE'} disabled={saveBusy} onPress={saveNewItem} />{saveError ? <Text style={s.errorText}>{saveError}</Text> : null}</>}{labMode && <><Text style={s.section}>Correction playground</Text>{attributes.map(attribute => <View key={attribute}><Text style={s.label}>{attribute}</Text><Text>{displayValue(result[attribute])}</Text><TextInput placeholder="Correct value (optional)" value={corrections[attribute] ?? ''} onChangeText={value => setCorrections({ ...corrections, [attribute]: value })} onEndEditing={async () => { if (corrections[attribute]) { try { await saveCorrection(result.imageId, attribute, result[attribute], corrections[attribute]); Alert.alert('Saved', 'Your correction was preserved.'); } catch (error) { Alert.alert('Correction not saved', friendlyApiError(error)); } } }} style={s.input} /></View>)}</>}{labMode && <Text selectable style={s.raw}>{result.rawResponse}</Text>}<Button title={labMode ? 'Back to AI Lab' : 'Retake Photo'} onPress={() => labMode ? setScreen('lab') : pick(true)} /><Button title="Back to Wardrobe" onPress={() => setScreen('wardrobe')} /></>}</>}</ScrollView></KeyboardAvoidingView></SafeAreaView>;

  const renderDetail = () => selected ? <SafeAreaView style={s.shell}><ScrollView contentContainerStyle={s.scrollContent}><WardrobeImage imageId={selected.imageId} variant="original" style={s.detailImage} /><Text style={s.title}>{selected.name}</Text>{selected.brand ? <Text style={s.sub}>{selected.brand}</Text> : null}{[['Category', selected.category], ['Type', selected.type], ['Color', selected.color], ['Pattern', selected.pattern], ['Fabric', selected.fabric], ['Fit', selected.fit], ['Style', selected.style], ['Occasions', selected.occasion], ['Seasons', selected.season]].map(([label, value]) => <View key={String(label)} style={s.detailRow}><Text style={s.detailLabel}>{label}</Text><Text>{displayValue(value)}</Text></View>)}<Text style={s.section}>AI DETAILS</Text><Text>Model: {selected.aiModelVersion}</Text><Text>Confidence: {Object.entries(selected.aiConfidence ?? {}).filter(([, value]) => value != null).map(([key, value]) => `${key} ${Math.round(Number(value) * 100)}%`).join(' · ') || 'Not provided'}</Text><Text style={s.note}>Created: {selected.createdAt}</Text>{selected.userCorrected && <Text style={s.corrected}>Includes user corrections</Text>}<Button title="EDIT" onPress={() => { setDraft(draftFrom(selected)); setSaveError(''); setScreen('edit'); }} /><Button title="DELETE" color="#b42318" onPress={confirmDelete} /><Button title="Back to Wardrobe" onPress={() => setScreen('wardrobe')} /></ScrollView></SafeAreaView> : null;

  const renderEdit = () => <SafeAreaView style={s.shell}><KeyboardAvoidingView style={s.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}><ScrollView contentContainerStyle={s.scrollContent} keyboardShouldPersistTaps="handled"><Text style={s.title}>EDIT CLOTHING</Text>{renderEditor()}<Button title={saveBusy ? 'Saving…' : 'SAVE CHANGES'} disabled={saveBusy} onPress={saveItemEdits} />{saveError ? <Text style={s.errorText}>{saveError}</Text> : null}<Button title="Cancel" onPress={() => setScreen('detail')} /></ScrollView></KeyboardAvoidingView></SafeAreaView>;

  const renderLab = () => { const installed = models.filter(model => model.status === 'installed'); const future = models.filter(model => model.status !== 'installed'); return <SafeAreaView style={s.shell}><ScrollView contentContainerStyle={s.scrollContent}><Text style={s.title}>AI MODEL LAB</Text><Text style={s.section}>BACKEND CONNECTION</Text><Text selectable style={s.url}>{API_CONFIGURED ? API_URL : 'EXPO_PUBLIC_API_URL is not configured'}</Text><View style={s.statusRow}><View style={[s.dot, connection.state === 'connected' ? s.green : connection.state === 'error' ? s.red : s.gray]} /><Text>{connection.state === 'checking' ? 'Checking…' : connection.state === 'connected' ? 'Connected' : connection.state === 'error' ? 'Unable to connect' : 'Not tested'}</Text></View>{connection.detail ? <Text selectable style={s.note}>{connection.detail}</Text> : null}<Button title="Test Backend Connection" disabled={connection.state === 'checking'} onPress={testConnection} />{modelsError ? <Text style={s.errorText}>{modelsError}</Text> : null}<Text style={s.section}>INSTALLED MODELS</Text>{modelsLoading ? <Text>Loading model status…</Text> : installed.length ? installed.map(model => <Text key={model.id}>✓ {model.name} · Installed</Text>) : <Text>○ No installed model reported</Text>}<Text style={s.section}>FUTURE MODELS</Text>{modelsLoading ? <Text>Loading model status…</Text> : future.length ? future.map(model => <Text key={model.id}>○ {model.name} · Not Installed</Text>) : <Text>No future models reported</Text>}<Text style={s.note}>The normal wardrobe flow never downloads models.</Text><Button title="Select Lab Photo" onPress={() => pick(false, true)} /><Button title="Back to Wardrobe" onPress={() => setScreen('wardrobe')} /></ScrollView></SafeAreaView>; };

  if (screen === 'wardrobe') return renderWardrobe();
  if (screen === 'detail') return renderDetail();
  if (screen === 'edit') return renderEdit();
  if (screen === 'lab') return renderLab();
  return renderReview();
}

const s = StyleSheet.create({
  shell: { flex: 1, backgroundColor: '#faf8f3' }, flex: { flex: 1 }, list: { flex: 1 }, listContent: { padding: 20, paddingBottom: 48 }, scrollContent: { padding: 24, paddingBottom: 48 },
  title: { fontSize: 28, fontWeight: '700', marginBottom: 6, color: '#211f1c' }, sub: { marginBottom: 20, color: '#716b64' }, section: { fontSize: 18, fontWeight: '700', marginTop: 24, marginBottom: 10, color: '#211f1c' },
  primaryButton: { backgroundColor: '#211f1c', borderRadius: 8, padding: 14, alignItems: 'center', marginBottom: 16 }, primaryButtonText: { color: '#fff', fontWeight: '700' }, search: { backgroundColor: '#fff', borderWidth: 1, borderColor: '#e0d9d0', borderRadius: 8, padding: 12, marginBottom: 10 }, filterRow: { paddingBottom: 16 }, chip: { borderWidth: 1, borderColor: '#d8d0c7', borderRadius: 18, paddingHorizontal: 12, paddingVertical: 8, marginRight: 7, marginBottom: 7, backgroundColor: '#fff' }, chipSelected: { backgroundColor: '#211f1c', borderColor: '#211f1c' }, chipText: { color: '#514b45', fontSize: 13 }, chipTextSelected: { color: '#fff', fontSize: 13, fontWeight: '700' },
  card: { width: '48%', backgroundColor: '#fff', borderRadius: 10, marginBottom: 14, marginRight: '4%', overflow: 'hidden' }, cardImage: { width: '100%', height: 190, backgroundColor: '#eee8df', resizeMode: 'cover' }, imageFallback: { alignItems: 'center', justifyContent: 'center' }, imageFallbackText: { color: '#716b64', fontSize: 12 }, cardName: { fontWeight: '700', paddingHorizontal: 10, paddingTop: 9 }, cardMeta: { color: '#716b64', paddingHorizontal: 10, paddingBottom: 10, paddingTop: 3 }, empty: { alignItems: 'center', padding: 28, marginTop: 20 }, emptyTitle: { fontSize: 20, fontWeight: '700', textAlign: 'center', marginBottom: 8 }, emptyText: { color: '#716b64', textAlign: 'center', marginBottom: 18 }, link: { color: '#6b4eff', textAlign: 'center', marginTop: 18, padding: 12 }, guidance: { backgroundColor: '#f0ebe4', borderRadius: 10, padding: 14, marginVertical: 16 }, guidanceTitle: { fontWeight: '700', marginBottom: 6 }, photo: { width: '100%', height: 300, resizeMode: 'contain', marginBottom: 12, backgroundColor: '#eee8df' }, detailImage: { width: '100%', height: 380, resizeMode: 'contain', backgroundColor: '#eee8df', marginBottom: 18 },
  fieldLabel: { fontWeight: '700', textTransform: 'capitalize', marginTop: 16, marginBottom: 7 }, input: { borderWidth: 1, borderColor: '#d8d0c7', backgroundColor: '#fff', padding: 11, marginBottom: 5, borderRadius: 7 }, chips: { flexDirection: 'row', flexWrap: 'wrap' }, stage: { color: '#6b4eff', marginVertical: 14, textAlign: 'center' }, errorBox: { backgroundColor: '#fff0ef', borderRadius: 8, padding: 12, marginVertical: 14 }, errorText: { color: '#a3261a', marginVertical: 8 }, warningBox: { backgroundColor: '#fff8df', borderRadius: 8, padding: 12, marginBottom: 10 }, warningText: { color: '#735500' }, label: { fontWeight: '700', textTransform: 'capitalize', marginTop: 14 }, raw: { backgroundColor: '#f2eee8', padding: 10, marginVertical: 14 }, detailRow: { borderBottomWidth: 1, borderBottomColor: '#eee8df', paddingVertical: 11 }, detailLabel: { color: '#716b64', fontSize: 12, textTransform: 'uppercase', marginBottom: 3 }, corrected: { color: '#18864b', marginVertical: 10 }, note: { color: '#716b64', marginVertical: 10 }, url: { fontFamily: 'Courier', fontSize: 13, marginBottom: 12, flexShrink: 1 }, statusRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 }, dot: { width: 10, height: 10, borderRadius: 5 }, green: { backgroundColor: '#18864b' }, red: { backgroundColor: '#c4382b' }, gray: { backgroundColor: '#888' },
});
