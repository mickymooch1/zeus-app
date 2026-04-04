import React, { useState } from 'react';
import { View, TextInput, TouchableOpacity, Text, StyleSheet } from 'react-native';

export function InputBar({ onSend, disabled }) {
  const [value, setValue] = useState('');

  const handleSend = () => {
    const text = value.trim();
    if (!text || disabled) return;
    onSend(text);
    setValue('');
  };

  const canSend = !disabled && value.trim().length > 0;

  return (
    <View style={styles.container}>
      <TextInput
        style={styles.input}
        value={value}
        onChangeText={setValue}
        placeholder="Ask Zeus anything..."
        placeholderTextColor="#555"
        multiline
        maxLength={4000}
        editable={!disabled}
      />
      <TouchableOpacity
        style={[styles.sendBtn, !canSend && styles.sendBtnDisabled]}
        onPress={handleSend}
        disabled={!canSend}
        activeOpacity={0.7}
      >
        <Text style={styles.sendBtnText}>⚡</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    padding: 12,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.07)',
    backgroundColor: 'rgba(0,0,0,0.2)',
  },
  input: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.3)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.1)',
    borderRadius: 10,
    padding: 10,
    color: '#e2d9f3',
    fontSize: 14,
    maxHeight: 100,
    marginRight: 8,
  },
  sendBtn: {
    width: 40, height: 40, borderRadius: 10,
    backgroundColor: '#a78bfa',
    alignItems: 'center', justifyContent: 'center',
  },
  sendBtnDisabled: { opacity: 0.4 },
  sendBtnText: { fontSize: 18, color: '#fff' },
});
