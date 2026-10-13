const PLAIN = { "İ": "i", "I": "i", "ı": "i", "Ç": "c", "ç": "c", "Ş": "s", "ş": "s", "Ğ": "g", "ğ": "g", "Ö": "o", "ö": "o", "Ü": "u", "ü": "u" };

// The same folding as the server's search (domain/search.py): Turkish letters and their plain forms match each other,
// so "api" finds "API" and "cinar" finds "Çınar". Turkish lower-casing alone would turn "API" into "apı".
export function searchFold(value) {
  return String(value ?? "").normalize("NFC").replace(/[İIıÇçŞşĞğÖöÜü]/g, char => PLAIN[char]).toLowerCase();
}
