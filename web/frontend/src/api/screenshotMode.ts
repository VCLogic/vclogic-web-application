type Identity = { vc_slug: string; display_name: string; firm?: string };
const normalizedWords = (value: string) => value.trim().toLowerCase().replace(/[\s_-]+/g, ' ');
const storageKey = 'vclogic-screenshot-mode';

export function screenshotMode(): boolean {
  const parameter = new URLSearchParams(window.location.search).get('screenshots');
  if (parameter !== null) sessionStorage.setItem(storageKey, parameter === '1' ? '1' : '0');
  return sessionStorage.getItem(storageKey) === '1';
}

const escapePattern = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

export function createScreenshotMask(identities: Identity[]) {
  const unique = [...new Map(identities.map(row => [row.vc_slug, row])).values()]
    .sort((a, b) => a.vc_slug.localeCompare(b.vc_slug));
  const aliases = new Map(unique.map((row, index) => [row.vc_slug, `investor-${index + 1}`]));
  const words = new Map<string, string>();
  const remember = (value: string, replacement: string) => words.set(normalizedWords(value), replacement);
  const firms = new Set(identities.map(row => row.firm?.trim()).filter((firm): firm is string => !!firm));
  for (const [index, row] of unique.entries()) {
    const label = `Investor #${index + 1}`;
    const name = row.display_name.replace(/-like Investor$/i, '').trim();
    remember(row.display_name, label);
    remember(name, label);
    // Public quotations often identify an investor using only a first or last name.
    for (const part of name.split(/\s+/)) if (part.length > 2) remember(part, label);
    // Generated wikis can omit firm metadata while the slug still encodes it.
    const nameSlug = name.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    if (nameSlug && row.vc_slug.startsWith(`${nameSlug}-`)) firms.add(row.vc_slug.slice(nameSlug.length + 1).replaceAll('-', ' '));
  }
  for (const firm of firms) remember(firm, 'Investment firm');
  const names = [...words.keys()].filter(Boolean).sort((a, b) => b.length - a.length);
  const pattern = names.length ? new RegExp(`\\b(?:${names.map(name => name.split(' ').map(escapePattern).join('[\\s_-]+')).join('|')})\\b`, 'gi') : null;
  const slugs = [...aliases.keys()].sort((a, b) => b.length - a.length);
  const slugPattern = slugs.length ? new RegExp(slugs.map(escapePattern).join('|'), 'g') : null;
  function text(value: string): string {
    // External links and image URLs can identify a person even without a name.
    let masked = value.replace(/https?:\/\/[^\s<>"')\]]+/gi, 'source-omitted');
    if (slugPattern) masked = masked.replace(slugPattern, slug => aliases.get(slug)!);
    if (pattern) masked = masked.replace(pattern, name => words.get(normalizedWords(name))!);
    return masked;
  }
  function mask<T>(value: T): T {
    if (typeof value === 'string') return text(value) as T;
    if (Array.isArray(value)) return value.map(item => mask(item)) as T;
    if (!value || typeof value !== 'object') return value;
    return Object.fromEntries(Object.entries(value).map(([key, item]) => {
      if (key === 'portrait_path') return [key, '/investor-placeholder.svg'];
      if (key === 'portrait_alt') return [key, 'Anonymous investor placeholder'];
      if (['source_url', 'source_profile_url', 'source_image_url', 'photo_attribution'].includes(key)) return [key, ''];
      return [aliases.get(key) ?? key, mask(item)];
    })) as T;
  }
  function originalPath(path: string): string {
    return path.replace(/\binvestor-\d+\b/g, alias => [...aliases].find(([, value]) => value === alias)?.[0] ?? alias);
  }
  return { mask, originalPath };
}

let prepared: Promise<ReturnType<typeof createScreenshotMask>> | undefined;
export function screenshotMask() {
  return prepared ??= Promise.all([
    fetch('/api/settings/investors'), fetch('/api/investors?include_unavailable=true'),
  ]).then(async responses => {
    if (responses.some(response => !response.ok)) throw new Error('Cannot prepare anonymized screenshot mode.');
    const payloads = await Promise.all(responses.map(response => response.json()));
    return createScreenshotMask(payloads.flatMap(payload => payload.investors));
  }).catch(() => { prepared = undefined; throw new Error('Cannot prepare anonymized screenshot mode.'); });
}
