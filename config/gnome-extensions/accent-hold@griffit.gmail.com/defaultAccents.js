// Default accent table: base key -> list of accented variants.
// Users can override this from the preferences (the `accents` GSettings key).

// Parse a user table (JSON text) and check its shape: an object whose values
// are arrays of non-empty strings. Returns the table, or null when the text
// is not JSON or not shaped like a table, so the caller can fall back to the
// built-in one instead of failing later on a key press.
export function parseTable(json) {
    let table;
    try {
        table = JSON.parse(json);
    } catch {
        return null;
    }
    if (typeof table !== 'object' || table === null || Array.isArray(table))
        return null;
    for (const [base, variants] of Object.entries(table)) {
        if (base === '' || !Array.isArray(variants))
            return null;
        if (!variants.every(v => typeof v === 'string' && v !== ''))
            return null;
    }
    return table;
}

export const DEFAULT_ACCENTS = {
    'a': ['á', 'à', 'ä', 'â', 'ã', 'å', 'æ'],
    'A': ['Á', 'À', 'Ä', 'Â', 'Ã', 'Å', 'Æ'],
    'c': ['ç', 'ć', 'č'],
    'C': ['Ç', 'Ć', 'Č'],
    'e': ['é', 'è', 'ë', 'ê', 'ē', 'ė', 'ę'],
    'E': ['É', 'È', 'Ë', 'Ê', 'Ē', 'Ė', 'Ę'],
    'i': ['í', 'ï', 'î', 'ì', 'ī', 'į'],
    'I': ['Í', 'Ï', 'Î', 'Ì', 'Ī', 'Į'],
    'n': ['ñ', 'ń'],
    'N': ['Ñ', 'Ń'],
    'o': ['ó', 'ö', 'ò', 'ô', 'õ', 'ø', 'œ'],
    'O': ['Ó', 'Ö', 'Ò', 'Ô', 'Õ', 'Ø', 'Œ'],
    'u': ['ú', 'ü', 'ù', 'û', 'ū'],
    'U': ['Ú', 'Ü', 'Ù', 'Û', 'Ū'],
    'y': ['ý', 'ÿ'],
    'Y': ['Ý', 'Ÿ'],
    's': ['ß', 'ś', 'š'],
    'S': ['Ś', 'Š'],
    'z': ['ž', 'ź', 'ż'],
    'Z': ['Ž', 'Ź', 'Ż'],
};
