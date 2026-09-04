import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Ionicons from '@expo/vector-icons/Ionicons';
import { themes, useTheme } from '../theme';
import { Text } from './ui';

export function ThemePicker() {
  const { theme, setTheme, saving, storageError } = useTheme();
  const colors = theme.colors;
  return <View>
    <Text style={styles.title}>Appearance</Text>
    <Text style={[styles.description, { color: colors.muted }]}>A different mood, whenever you like.</Text>
    <View accessibilityRole="radiogroup" accessibilityLabel="App theme" style={styles.options}>
      {Object.values(themes).map(option => {
        const selected = theme.id === option.id;
        return <Pressable key={option.id} accessibilityRole="radio" accessibilityLabel={`${option.name} theme`}
          accessibilityState={{ checked: selected }} aria-checked={selected} onPress={() => setTheme(option.id)}
          style={({ pressed }) => [styles.option, { backgroundColor: colors.surface, borderColor: selected ? colors.accent : colors.border, opacity: pressed ? 0.7 : 1 }]}>
          <View style={[styles.preview, { backgroundColor: option.colors.background }]}>
            <View style={styles.previewHeader}>
              <View style={[styles.previewLine, { backgroundColor: option.colors.text }]} />
              <View style={[styles.previewDot, { backgroundColor: option.colors.accent }]} />
            </View>
            <View style={styles.previewTiles}>
              <View style={[styles.previewTile, { backgroundColor: option.colors.elevated }]} />
              <View style={[styles.previewTile, { backgroundColor: option.colors.accentSoft }]} />
            </View>
            <View style={[styles.previewButton, { backgroundColor: option.colors.accent }]} />
          </View>
          <Text style={[styles.name, { color: selected ? colors.accent : colors.text }]}>{option.name}</Text>
          <Ionicons name={selected ? 'checkmark-circle' : 'ellipse-outline'} size={20} color={selected ? colors.accent : colors.muted} />
        </Pressable>;
      })}
    </View>
    <Text accessibilityLiveRegion="polite" style={[styles.caption, { color: colors.muted }]}>{theme.name} selected{saving ? ' · Saving…' : storageError ? '' : ' · Remembered on this device'}</Text>
    {storageError ? <Text accessibilityRole="alert" style={{ color: colors.danger }}>{storageError}</Text> : null}
  </View>;
}

const styles = StyleSheet.create({
  title: { fontSize: 20, lineHeight: 28, fontWeight: '600' }, description: { marginTop: 4, marginBottom: 18 },
  options: { flexDirection: 'row', gap: 10 }, option: { flex: 1, minWidth: 0, padding: 9, borderRadius: 16, borderWidth: 1.5, alignItems: 'center', gap: 7 },
  preview: { width: '100%', height: 80, borderRadius: 9, padding: 9, gap: 9 }, previewHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  previewLine: { width: '40%', height: 3, borderRadius: 2 }, previewDot: { width: 5, height: 5, borderRadius: 3 },
  previewTiles: { flexDirection: 'row', gap: 5, flex: 1 }, previewTile: { flex: 1, borderRadius: 4 },
  previewButton: { height: 5, borderRadius: 3 }, name: { fontSize: 12, fontWeight: '600' }, caption: { fontSize: 12, marginTop: 12 },
});
