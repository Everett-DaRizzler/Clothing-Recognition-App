import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import Ionicons from '@expo/vector-icons/Ionicons';
import { useTheme } from '../theme';
import { Text } from './ui';

export type MainTab = 'wardrobe' | 'outfits' | 'profile';
type IconName = React.ComponentProps<typeof Ionicons>['name'];
const tabs: { id: MainTab; label: string; icon: IconName; active: IconName }[] = [
  { id: 'wardrobe', label: 'My Wardrobe', icon: 'shirt-outline', active: 'shirt' },
  { id: 'outfits', label: 'My Outfits', icon: 'layers-outline', active: 'layers' },
  { id: 'profile', label: 'Profile', icon: 'person-outline', active: 'person' },
];

export function AppChrome({ children, activeTab, canGoBack, onBack, onSettings, onTab, settingsOpen }: {
  children: React.ReactNode; activeTab: MainTab; canGoBack: boolean; onBack: () => void;
  onSettings: () => void; onTab: (tab: MainTab) => void; settingsOpen: boolean;
}) {
  const { theme: { colors, dark } } = useTheme();
  return <SafeAreaView style={[styles.root, { backgroundColor: colors.background }]} edges={['top', 'bottom']}>
    <StatusBar style={dark ? 'light' : 'dark'} />
    <View style={[styles.frame, { backgroundColor: colors.background }]}>
      <View style={[styles.header, { borderBottomColor: colors.border }]}>
        <Pressable accessibilityRole="button" accessibilityLabel="Go back" accessibilityState={{ disabled: !canGoBack }}
          disabled={!canGoBack} onPress={onBack} style={({ pressed }) => [styles.iconButton, { opacity: !canGoBack ? 0.28 : pressed ? 0.6 : 1 }]}>
          <Ionicons name="arrow-back" size={24} color={colors.text} />
        </Pressable>
        <View accessible accessibilityLabel="AI Wardrobe" style={styles.brand}>
          <View style={[styles.brandDot, { backgroundColor: colors.accent }]} />
          <Text style={[styles.wordmark, { color: colors.text }]}>WARDROBE</Text>
        </View>
        <Pressable accessibilityRole="button" accessibilityLabel="Settings" accessibilityState={{ selected: settingsOpen }}
          onPress={onSettings} style={({ pressed }) => [styles.iconButton, { backgroundColor: settingsOpen ? colors.accentSoft : 'transparent', opacity: pressed ? 0.6 : 1 }]}>
          <Ionicons name="settings-outline" size={24} color={settingsOpen ? colors.accent : colors.text} />
        </Pressable>
      </View>
      <View style={styles.content}>{children}</View>
      <View accessibilityRole="tablist" style={[styles.tabBar, { backgroundColor: colors.surface, borderTopColor: colors.border }]}>
        {tabs.map(tab => {
          const selected = activeTab === tab.id;
          return <Pressable key={tab.id} accessibilityRole="tab" accessibilityLabel={tab.label}
            accessibilityState={{ selected }} aria-selected={selected} onPress={() => onTab(tab.id)}
            style={({ pressed }) => [styles.tab, { opacity: pressed ? 0.6 : 1 }]}>
            <View style={[styles.tabIcon, { backgroundColor: selected ? colors.accentSoft : 'transparent' }]}>
              <Ionicons name={selected ? tab.active : tab.icon} size={24} color={selected ? colors.accent : colors.muted} />
            </View>
            <View style={[styles.activeDot, { backgroundColor: selected ? colors.accent : 'transparent' }]} />
          </Pressable>;
        })}
      </View>
    </View>
  </SafeAreaView>;
}

const styles = StyleSheet.create({
  root: { flex: 1 }, frame: { flex: 1, width: '100%', maxWidth: 560, alignSelf: 'center', overflow: 'hidden' },
  header: { height: 68, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 12, borderBottomWidth: StyleSheet.hairlineWidth },
  iconButton: { width: 48, height: 48, alignItems: 'center', justifyContent: 'center', borderRadius: 16 },
  brand: { flexDirection: 'row', alignItems: 'center', gap: 8 }, brandDot: { width: 6, height: 6, borderRadius: 3 },
  wordmark: { fontSize: 12, fontWeight: '700', letterSpacing: 3 }, content: { flex: 1, minHeight: 0 },
  tabBar: { flexDirection: 'row', justifyContent: 'space-around', paddingTop: 8, paddingBottom: 6, borderTopWidth: StyleSheet.hairlineWidth },
  tab: { flex: 1, minHeight: 58, alignItems: 'center', justifyContent: 'center', gap: 5 },
  tabIcon: { width: 64, height: 40, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  activeDot: { width: 4, height: 4, borderRadius: 2 },
});
