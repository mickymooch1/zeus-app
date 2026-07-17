import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import en from './locales/en.json';
import fr from './locales/fr.json';
import es from './locales/es.json';
import de from './locales/de.json';
import pt from './locales/pt.json';
import it from './locales/it.json';
import nl from './locales/nl.json';
import ru from './locales/ru.json';
import ja from './locales/ja.json';
import ko from './locales/ko.json';
import zh from './locales/zh.json';
import ar from './locales/ar.json';
import th from './locales/th.json';

// Locales that read right-to-left. Arabic ships fully translated, so without this
// its text rendered correctly inside an LTR layout — worse than not shipping it.
const RTL_LANGUAGES = new Set(['ar', 'he', 'fa', 'ur']);

function applyDocumentDirection() {
  if (typeof document === 'undefined') return;
  // Must read the RESOLVED language, not the requested one. A Hebrew visitor
  // requests 'he', which has no resources and falls back to English text — keying
  // off the request would render that English in an RTL layout. resolvedLanguage
  // also collapses region codes ('ar-EG' -> 'ar').
  const base = (i18n.resolvedLanguage || i18n.language || 'en').split('-')[0].toLowerCase();
  document.documentElement.dir = RTL_LANGUAGES.has(base) ? 'rtl' : 'ltr';
  document.documentElement.lang = base;
}

// Registered before init() so the languageChanged that init itself emits is caught.
i18n.on('languageChanged', applyDocumentDirection);

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      fr: { translation: fr },
      es: { translation: es },
      de: { translation: de },
      pt: { translation: pt },
      it: { translation: it },
      nl: { translation: nl },
      ru: { translation: ru },
      ja: { translation: ja },
      ko: { translation: ko },
      zh: { translation: zh },
      ar: { translation: ar },
      th: { translation: th },
    },
    fallbackLng: 'en',
    interpolation: { escapeValue: false },
    react: { useSuspense: false },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
      lookupLocalStorage: 'zeus_beats_lang',
    },
  }, () => applyDocumentDirection());

export default i18n;
