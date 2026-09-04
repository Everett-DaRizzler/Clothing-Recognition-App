import React from 'react';
import { Text as NativeText, TextInput as NativeTextInput, TextProps, TextInputProps, ButtonProps, Pressable, StyleSheet } from 'react-native';
import { useTheme } from '../theme';

export function Text({ style, ...props }: TextProps) {
  const { theme } = useTheme();
  return <NativeText {...props} style={[{ color: theme.colors.text, fontSize: 14, lineHeight: 21 }, style]} />;
}

export const TextInput = React.forwardRef<NativeTextInput, TextInputProps>(function TextInput({ style, ...props }, ref) {
  const { theme } = useTheme();
  return <NativeTextInput ref={ref} placeholderTextColor={theme.colors.muted} selectionColor={theme.colors.accent}
    keyboardAppearance={theme.dark ? 'dark' : 'light'} {...props}
    style={[{ color: theme.colors.text, fontSize: 16, minHeight: 48 }, style]} />;
});

export function Button({ title, onPress, color, disabled, accessibilityLabel, testID }: ButtonProps) {
  const { theme: { colors } } = useTheme();
  const destructive = color === '#b42318';
  return <Pressable accessibilityRole="button" accessibilityLabel={accessibilityLabel ?? title}
    accessibilityState={{ disabled: !!disabled }} disabled={disabled} testID={testID} onPress={onPress}
    style={({ pressed }) => [styles.button, { backgroundColor: destructive ? colors.dangerSoft : colors.elevated,
      borderColor: colors.border, opacity: disabled ? 0.45 : pressed ? 0.7 : 1 }]}>
    <Text style={{ color: destructive ? colors.danger : colors.accent, fontWeight: '600', textAlign: 'center' }}>{title}</Text>
  </Pressable>;
}

const styles = StyleSheet.create({ button: { minHeight: 48, paddingVertical: 12, paddingHorizontal: 16, borderWidth: 1, borderRadius: 14, alignItems: 'center', justifyContent: 'center', marginVertical: 5 } });
