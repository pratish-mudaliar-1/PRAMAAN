/**
 * src/api/auth.ts
 *
 * Dev-mode token generation.
 * In production this would redirect to the OIDC IdP.
 *
 * The backend uses HS256 with secret "dev-only-secret-change-in-prod"
 * (AUTH_DEV_JWT_SECRET default) when AUTH_JWKS_URL is empty and
 * environment != "production".
 *
 * We replicate the same payload here so the frontend can generate its
 * own short-lived token for the SIH demo — no separate login server needed.
 */

import { setToken } from './client';

/** JWT base64url encode (no padding). */
function b64url(obj: object): string {
  return btoa(JSON.stringify(obj))
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');
}

/**
 * Generate a dev HS256 JWT in the browser using the Web Crypto API.
 * Uses the same secret the backend defaults to.
 */
async function signHS256(header: object, payload: object, secret: string): Promise<string> {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw',
    enc.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  const msg = `${b64url(header)}.${b64url(payload)}`;
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(msg));
  const sigB64 = btoa(String.fromCharCode(...new Uint8Array(sig)))
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');
  return `${msg}.${sigB64}`;
}

export interface DevTokenOptions {
  subject?: string;
  roles?: string[];
  ttlSeconds?: number;
}

/**
 * Create and store a dev token.  Call once on app load.
 * Returns the raw token string.
 */
export async function bootstrapDevToken(opts: DevTokenOptions = {}): Promise<string> {
  const {
    subject = 'dev-national-admin',
    roles = ['national_admin'],
    ttlSeconds = 86_400, // 24 h
  } = opts;

  const secret = 'dev-only-secret-change-in-prod';
  const now = Math.floor(Date.now() / 1000);

  const header = { alg: 'HS256', typ: 'JWT' };
  const payload = {
    sub: subject,
    iss: 'http://localhost:8000/dev-oidc',
    aud: 'pramaan-api',
    iat: now,
    exp: now + ttlSeconds,
    roles,
  };

  const token = await signHS256(header, payload, secret);
  setToken(token);
  return token;
}

/** Decode a JWT's payload (no verification). */
export function decodePayload(token: string): Record<string, unknown> {
  try {
    const part = token.split('.')[1];
    return JSON.parse(atob(part.replace(/-/g, '+').replace(/_/g, '/')));
  } catch {
    return {};
  }
}

/** Return true if the stored token is still valid (with 60 s leeway). */
export function isTokenValid(): boolean {
  const token = localStorage.getItem('pramaan_token');
  if (!token) return false;
  const { exp } = decodePayload(token) as { exp?: number };
  if (!exp) return false;
  return exp > Math.floor(Date.now() / 1000) + 60;
}
