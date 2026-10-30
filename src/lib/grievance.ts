/*
 * Helpers for showing a GrievanceGuide. They only re-present text the API returned: nothing
 * here adds a forum, number, date or time limit.
 */

export interface ForumNote {
  /** The note without its trailing source sentence. */
  text: string;
  sourceUrl: string | null;
  asOf: string | null;
}

/** The API ends a verified forum note with "Source: <url> (as of <date>)." Split that off. */
const SOURCE_SENTENCE = /\s*Source:\s*(\S+?)\s*\(as of ([^)]+)\)\.?/i;

export function parseForumNote(note: string): ForumNote {
  const match = SOURCE_SENTENCE.exec(note);
  if (!match) return { text: note.trim(), sourceUrl: null, asOf: null };
  return {
    text: `${note.slice(0, match.index)} ${note.slice(match.index + match[0].length)}`
      .replace(/\s+/g, ' ')
      .trim(),
    sourceUrl: safeHttpsUrl(match[1]),
    asOf: match[2].trim(),
  };
}

export function safeHttpsUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' ? url.href : null;
  } catch {
    return null;
  }
}

export type ContactPart =
  | { kind: 'text'; value: string }
  | { kind: 'link'; value: string; href: string; external: boolean };

// URLs, e-mail addresses, and phone numbers of 5 to 13 digits (optionally with + - or spaces).
const CONTACT_TOKEN =
  /(https?:\/\/[^\s;,)]+)|([\w.+-]+@[\w-]+(?:\.[\w-]+)+)|(?<![\w/.-])(\+?\d[\d -]{3,16}\d)(?![\d-])/g;

/** Splits text so the contact values already in it can be rendered as links. */
export function splitContacts(text: string): ContactPart[] {
  const parts: ContactPart[] = [];
  let last = 0;
  for (const match of text.matchAll(CONTACT_TOKEN)) {
    const [token, url, email, phone] = match;
    const start = match.index;
    let value = token;
    let href: string | null = null;
    let external = false;

    if (url) {
      value = url.replace(/[.]+$/, '');
      href = safeHttpsUrl(value);
      external = true;
    } else if (email) {
      value = email.replace(/[.]+$/, '');
      href = `mailto:${value}`;
    } else if (phone) {
      const digits = phone.replace(/\D/g, '');
      const isDate = /^\d{4}-\d{2}-\d{2}$/.test(phone);
      if (!isDate && digits.length >= 5 && digits.length <= 13)
        href = `tel:${phone.startsWith('+') ? '+' : ''}${digits}`;
    }

    if (!href) continue;
    if (start > last) parts.push({ kind: 'text', value: text.slice(last, start) });
    parts.push({ kind: 'link', value, href, external });
    last = start + value.length;
  }
  if (last < text.length) parts.push({ kind: 'text', value: text.slice(last) });
  return parts;
}
