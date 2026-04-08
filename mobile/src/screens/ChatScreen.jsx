import React, { useRef, useEffect, useCallback } from 'react';
import {
  View, FlatList, StyleSheet, StatusBar,
  KeyboardAvoidingView, Platform, Text, TouchableOpacity,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useHeaderHeight } from '@react-navigation/elements';
import { useZeusSocket } from '../hooks/useZeusSocket';
import { MessageBubble } from '../components/MessageBubble';
import { InputBar } from '../components/InputBar';

export function ChatScreen({ navigation, route }) {
  const { messages, streaming, sendMessage, newSession, loadSession } = useZeusSocket();
  const flatListRef = useRef(null);
  const loadedSessionRef = useRef(null);

  // useHeaderHeight() returns the exact height of the navigation header including
  // status bar on iOS. Using it as keyboardVerticalOffset tells KeyboardAvoidingView
  // how far its top edge is from the screen top, so it calculates the correct
  // amount to shift content when the keyboard appears.
  const headerHeight = useHeaderHeight();

  useEffect(() => {
    const sessionId = route.params?.sessionId;
    if (sessionId && sessionId !== loadedSessionRef.current) {
      loadedSessionRef.current = sessionId;
      loadSession(sessionId);
    }
  }, [route.params?.sessionId, loadSession]);

  const handleLogout = useCallback(async () => {
    await AsyncStorage.removeItem('zeus_token');
    newSession();
    navigation.reset({ index: 0, routes: [{ name: 'Login' }] });
  }, [navigation, newSession]);

  useEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <View style={{ flexDirection: 'row', alignItems: 'center', marginRight: 8 }}>
          <TouchableOpacity
            onPress={() => { loadedSessionRef.current = null; newSession(); }}
            style={{ marginRight: 12 }}
          >
            <Text style={{ color: '#a78bfa', fontSize: 13, fontWeight: '600' }}>New</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={handleLogout} style={{ padding: 4 }}>
            <Text style={{ color: '#888', fontSize: 18 }}>⏻</Text>
          </TouchableOpacity>
        </View>
      ),
      headerLeft: () => (
        <TouchableOpacity onPress={() => navigation.navigate('Sessions')} style={{ marginLeft: 16 }}>
          <Text style={{ color: '#a78bfa', fontSize: 20 }}>☰</Text>
        </TouchableOpacity>
      ),
    });
  }, [navigation, newSession, handleLogout]);

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
    // KeyboardAvoidingView wraps the entire screen content (FlatList + InputBar).
    // behavior='padding' on iOS: adds bottom padding equal to keyboard height,
    //   pushing the InputBar up without resizing the view.
    // behavior='height' on Android: shrinks the view height so the InputBar
    //   stays anchored at the bottom above the keyboard.
    // keyboardVerticalOffset={headerHeight}: on both platforms the KAV sits below
    //   the navigation header, so we tell it to subtract that header height when
    //   computing how much to adjust — without this the adjustment overshoots.
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={headerHeight}
    >
      <StatusBar barStyle="light-content" backgroundColor="#0f0c29" />
      <FlatList
        ref={flatListRef}
        style={styles.list}
        data={messages}
        keyExtractor={item => String(item.id)}
        renderItem={renderMessage}
        contentContainerStyle={styles.listContent}
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
  container:   { flex: 1, backgroundColor: '#0f0c29' },
  // flex: 1 is critical — lets the FlatList contract when KAV shrinks the view
  // on Android (behavior='height'), so the InputBar is never pushed offscreen.
  list:        { flex: 1 },
  listContent: { padding: 16, paddingBottom: 8 },
  empty:       { flex: 1, alignItems: 'center', justifyContent: 'center', paddingTop: 80 },
  emptyIcon:   { fontSize: 36, marginBottom: 8 },
  emptyTitle:  { color: '#e2d9f3', fontSize: 16, fontWeight: '600', marginBottom: 4 },
  emptySub:    { color: '#555', fontSize: 12 },
});
