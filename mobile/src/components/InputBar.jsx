import React, { useState } from 'react';
import {
  View, TextInput, TouchableOpacity, Text, Image,
  StyleSheet, Alert,
} from 'react-native';
import { launchImageLibrary } from 'react-native-image-picker';

export function InputBar({ onSend, disabled }) {
  const [value, setValue] = useState('');
  const [imageAttachment, setImageAttachment] = useState(null); // {data, media_type, preview}

  // Fix 2: open gallery and convert selected image to base64
  const pickImage = () => {
    launchImageLibrary(
      {
        mediaType: 'photo',
        includeBase64: true,
        quality: 0.8,
        maxWidth: 1920,
        maxHeight: 1920,
      },
      (response) => {
        if (response.didCancel || response.errorCode) return;
        const asset = response.assets?.[0];
        if (!asset?.base64) {
          Alert.alert('Image Error', 'Could not read image data. Please try another image.');
          return;
        }
        setImageAttachment({
          data: asset.base64,
          media_type: asset.type || 'image/jpeg',
          preview: asset.uri,
        });
      },
    );
  };

  const removeImage = () => setImageAttachment(null);

  const handleSend = () => {
    const text = value.trim();
    if ((!text && !imageAttachment) || disabled) return;
    onSend(text, imageAttachment ?? null);
    setValue('');
    setImageAttachment(null);
  };

  const canSend = !disabled && (value.trim().length > 0 || imageAttachment !== null);

  return (
    <View style={styles.wrapper}>
      {imageAttachment && (
        <View style={styles.previewRow}>
          <View style={styles.previewThumb}>
            <Image source={{ uri: imageAttachment.preview }} style={styles.previewImage} />
            <TouchableOpacity style={styles.removeBtn} onPress={removeImage} activeOpacity={0.8}>
              <Text style={styles.removeBtnText}>×</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}
      <View style={styles.container}>
        <TouchableOpacity
          style={[styles.attachBtn, disabled && styles.attachBtnDisabled]}
          onPress={pickImage}
          disabled={disabled}
          activeOpacity={0.7}
        >
          <Text style={styles.attachBtnText}>📎</Text>
        </TouchableOpacity>
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
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.07)',
    backgroundColor: 'rgba(0,0,0,0.2)',
  },
  previewRow: {
    paddingHorizontal: 12,
    paddingTop: 10,
  },
  previewThumb: {
    position: 'relative',
    alignSelf: 'flex-start',
  },
  previewImage: {
    width: 80,
    height: 80,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.1)',
  },
  removeBtn: {
    position: 'absolute',
    top: -6,
    right: -6,
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: 'rgba(239,68,68,0.9)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  removeBtnText: {
    color: '#fff',
    fontSize: 14,
    lineHeight: 18,
    fontWeight: '700',
  },
  container: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    padding: 12,
  },
  attachBtn: {
    width: 40,
    height: 40,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.15)',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 8,
  },
  attachBtnDisabled: { opacity: 0.35 },
  attachBtnText: { fontSize: 18 },
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
