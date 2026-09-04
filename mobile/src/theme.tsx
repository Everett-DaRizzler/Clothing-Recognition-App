import React, { createContext, useContext, useEffect, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { createLatestThemeWriter } from './theme-storage';

export type ThemeId = 'midnight' | 'daylight' | 'evergreen';
export type Palette = {
  background: string; surface: string; elevated: string; border: string;
  text: string; muted: string; accent: string; onAccent: string; accentSoft: string;
  danger: string; dangerSoft: string; warning: string; warningSoft: string; success: string;
};
export type AppTheme = { id: ThemeId; name: string; description: string; dark: boolean; colors: Palette };

export const themes: Record<ThemeId, AppTheme> = {
  midnight: {
    id: 'midnight', name: 'Midnight', description: 'Quiet tones. A little after dark.', dark: true,
    colors: {
      background: '#0E121B', surface: '#181F2C', elevated: '#222C3C', border: '#344157',
      text: '#F2F5FC', muted: '#ADB9CC', accent: '#B6C6FF', onAccent: '#162044', accentSoft: '#283655',
      danger: '#FFB4AA', dangerSoft: '#392329', warning: '#F4D391', warningSoft: '#352E21', success: '#8FD8B0',
    },
  },
  daylight: {
    id: 'daylight', name: 'Daylight', description: 'Light, fresh, and easy on the eyes.', dark: false,
    colors: {
      background: '#F4F6FB', surface: '#FFFFFF', elevated: '#E8EDF6', border: '#CBD4E3',
      text: '#1B2538', muted: '#546178', accent: '#4256AB', onAccent: '#FFFFFF', accentSoft: '#E0E7FF',
      danger: '#A32C35', dangerSoft: '#FBE9EC', warning: '#775314', warningSoft: '#FFF3D6', success: '#236647',
    },
  },
  evergreen: {
    id: 'evergreen', name: 'Evergreen', description: 'Deep greens with a softer glow.', dark: true,
    colors: {
      background: '#0C1916', surface: '#1A3229', elevated: '#254337', border: '#406653',
      text: '#EFF8F2', muted: '#ABC4B7', accent: '#A7E6C5', onAccent: '#102E21', accentSoft: '#305441',
      danger: '#FFB4AA', dangerSoft: '#392629', warning: '#F4D391', warningSoft: '#352E21', success: '#A7E6C5',
    },
  },
};

const storageKey = '@ai-wardrobe/appearance';
type ThemeContextValue = { theme: AppTheme; ready: boolean; saving: boolean; storageError: string; setTheme: (id: ThemeId) => void };
const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [themeId, setThemeId] = useState<ThemeId>('midnight');
  const [ready, setReady] = useState(false);
  const [saving, setSaving] = useState(false);
  const [storageError, setStorageError] = useState('');
  useEffect(() => {
    let mounted = true;
    AsyncStorage.getItem(storageKey).then(saved => {
      if (mounted && saved && Object.prototype.hasOwnProperty.call(themes, saved)) setThemeId(saved as ThemeId);
    }).catch(() => {
      if (mounted) setStorageError('Your saved appearance could not be loaded.');
    }).finally(() => { if (mounted) setReady(true); });
    return () => { mounted = false; };
  }, []);

  const persistTheme = React.useMemo(() => createLatestThemeWriter(
    id => AsyncStorage.setItem(storageKey, id),
    saved => {
      setSaving(false);
      setStorageError(saved ? '' : 'Theme changed for now, but could not be saved on this device.');
    },
  ), []);
  const setTheme = (id: ThemeId) => {
    setThemeId(id);
    setSaving(true);
    setStorageError('');
    void persistTheme(id);
  };
  return <ThemeContext.Provider value={{ theme: themes[themeId], ready, saving, storageError, setTheme }}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const value = useContext(ThemeContext);
  if (!value) throw new Error('useTheme must be used inside ThemeProvider');
  return value;
}
