// frontend-modern/src/lib/domain.ts
/**
 * Domain/subdomain detection utilities
 */

/**
 * Hostname'den subdomain'i çıkar
 * Örnekler:
 * - fistikkafe.neso-moduler.vercel.app -> fistikkafe
 * - relaxkafe.neso-moduler.vercel.app -> relaxkafe
 * - neso-moduler.vercel.app -> null (ana domain)
 * - localhost:5173 -> null
 */
export function extractSubdomain(hostname: string): string | null {
  if (!hostname) return null;
  
  // Port'u temizle
  const host = hostname.split(':')[0];
  
  // localhost veya IP adresi ise subdomain yok
  if (host === 'localhost' || host === '127.0.0.1' || /^\d+\.\d+\.\d+\.\d+$/.test(host)) {
    return null;
  }
  
  const parts = host.split('.');
  
  // En az 3 parça olmalı (subdomain.domain.tld)
  if (parts.length < 3) {
    return null;
  }
  
  // İlk parça subdomain
  const subdomain = parts[0].toLowerCase();
  
  // Özel durumlar: www, api, www2 gibi
  if (['www', 'api', 'www2'].includes(subdomain)) {
    return null;
  }
  
  return subdomain;
}

/**
 * Mevcut hostname'den subdomain'i al
 */
export function getCurrentSubdomain(): string | null {
  if (typeof window === 'undefined') return null;
  return extractSubdomain(window.location.hostname);
}

/**
 * Domain'den tenant customization'ı yükle
 */
export async function loadTenantByDomain(domain: string, apiBaseUrl: string): Promise<any> {
  try {
    const response = await fetch(`${apiBaseUrl}/customization/domain/${encodeURIComponent(domain)}`);
    if (!response.ok) {
      return null;
    }
    return await response.json();
  } catch (error) {
    console.warn('Tenant customization yüklenemedi:', error);
    return null;
  }
}

