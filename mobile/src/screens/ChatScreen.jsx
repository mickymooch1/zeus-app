import React, { useRef, useEffect, useCallback } from 'react';
import {
  View, FlatList, StyleSheet, StatusBar,
  KeyboardAvoidingView, Platform, Text, TouchableOpacity,
} from 'react-native';
import { useHeaderHeight } from '@react-navigation/elements';
import { useZeusSocket } from '../hooks/useZeusSocket';
import { MessageBubble } from '../components/MessageBubble';
import { InputBar } from '../components/InputBar';

export function ChatScreen({ navigation, route }) {
  const { messages, streaming, sendMessage, newSession, loadSession } = useZeusSocket();
  const flatListRef = useRef(null);
  const loadedSessionRef = useRef(null); // prevents re-loading the same session on re-render
  const headerHeight = useHeaderHeight();

  // Fix 1: load session when navigating from the history screen
  useEffect(() => {
    const sessionId = route.params?.sessionId;
    if (sessionId && sessionId !== loadedSessionRef.current) {
      loadedSessionRef.current = sessionId;
      loadSession(sessionId);
    }
  }, [route.params?.sessionId, loadSession]);

  useEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <TouchableOpacity
          onPress={() => {
            loadedSessionRef.current = null;
            newSession();
          }}
          style={{ marginRight: 16 }}
        >
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

  const renderMessage = useCallback(({ item, index }) => (
    <MessageBubble
      message={item}
      isStreaming={streaming && index === messages.length - 1 && item.role === 'zeus'}
    />
  ), [streaming, messages.length]);

  useEffect(() => {
    if (messages.length > 0) {
      flatListRef.current?.scrollToEnd({ animated: true });
    }
  }, [messages.length]);

  return (
    // Fix 3: KeyboardAvoidingView as the outermost container
    // behavior='padding' on iOS pushes content up; 'height' on Android shrinks the view
    // headerHeight from useHeaderHeight() gives the exact navigation bar offset for iOS
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={Platform.OS === 'ios' ? headerHeight : 0}
    >
      <StatusBar barStyle="light-content" backgroundColor="#0f0c29" />
      <FlatList
        ref={flatListRef}
        data={messages}
        keyExtractor={item => String(item.id)}
        renderItem={renderMessage}
        contentContainerStyle={styles.list}
        keyboardDismissMode="on-drag"
        keyboardShouldPersistTaps="handled"
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
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f0c29' },
  list: { padding: 16, paddingBottom: 8 },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingTop: 80 },
  emptyIcon: { fontSize: 36, marginBottom: 8 },
  emptyTitle: { color: '#e2d9f3', fontSize: 16, fontWeight: '600', marginBottom: 4 },
  emptySub: { color: '#555', fontSize: 12 },
});
