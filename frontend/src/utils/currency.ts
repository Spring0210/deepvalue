const SYMBOLS: Record<string, string> = {
  USD: '$', HKD: 'HK$', CNY: '¥', EUR: '€', GBP: '£',
  JPY: '¥', CAD: 'C$', AUD: 'A$', KRW: '₩', INR: '₹',
  SGD: 'S$', TWD: 'NT$',
}

export function getCurrencySymbol(currency?: string | null): string {
  return SYMBOLS[currency ?? 'USD'] ?? (currency ?? '$')
}
