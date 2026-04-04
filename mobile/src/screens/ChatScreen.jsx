import React, { useRef, useEffect, useCallback } from 'react';
import {
  View, FlatList, StyleSheet, StatusBar,
  KeyboardAvoidingView, Platform, Text, TouchableOpacity,
} from 'react-native';
import { useZeusSocket } from '../hooks/useZeusSocket';
import { MessageBubble } from '../components/MessageBubble';
import { InputBar } from '../components/InputBar';

export function ChatScreen({ navigation, route }) {
  const { messages, streaming, sendMessage, newSession } = useZeusSocket();
  const flatListRef = useRef(null);

  const renderMessage = useCallback(({ item, index }) => (
    <MessageBubble
      message={item}
      isStreaming={streaming && index === messages.length - 1 && item.role === 'zeus'}
    />
  ), [streaming, messages.length]);

  useEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <TouchableOpacity onPress={newSession} style={{ marginRight: 16 }}>
          <Text style={{ color: '#a78bfa', fontSize: 13, fontWeight: '600' }}>New</Text>
        </TouchableOpacity>
      ),
      headerLeft: () => (
        <TouchableOpacity onPress={() => navigation.navigate('Sessions')} style={{ marginLeft: 16 }}>
          <Text style={{ color: '#a78bfa', fontSize: 20 }}>☰</Text>
        </TouchableOpacity>
      ),
    });
  }, [navigation, newSession]);

  useEffect(() => {
    if (messages.length > 0) {
      flatListRef.current?.scrollToEnd({ animated: true });
    }
  }, [messages.length]);

  return (
    <View style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#0f0c29" />
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
      >
        <FlatList
          ref={flatListRef}
          data={messages}
          keyExtractor={item => String(item.id)}
          renderItem={renderMessage}
          contentContainerStyle={styles.list}
          onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: true })}
          ListEmptyComponent={
            <View style={styles.empty}>
              <Text style={styles.emptyIcon}>⚡</Text>
              <Text style={styles.emptyTitle}>Ask Zeus anything.</Text>
              <Text style={styles.emptySub}>Websites · Research · Emails</Text>
            </View>
          }
        />
        <InputBar onSend={sendMessage} disabled={streaming} />
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f0c29' },
  flex: { flex: 1 },
  list: { padding: 16, paddingBottom: 8 },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingTop: 80 },
  emptyIcon: { fontSize: 36, marginBottom: 8 },
  emptyTitle: { color: '#e2d9f3', fontSize: 16, fontWeight: '600', marginBottom: 4 },
  emptySub: { color: '#555', fontSize: 12 },
});
