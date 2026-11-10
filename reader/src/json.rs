//! Just enough JSON for the pipe's headers: TurboHUD's requests are small objects of
//! numbers, strings, lists and nulls; the answers are written with `Value::write`.

use std::collections::BTreeMap;
use std::fmt::Write as _;

#[derive(Clone, Debug, PartialEq)]
pub enum Value {
    Null,
    Bool(bool),
    Int(i128),
    Float(f64),
    Str(String),
    List(Vec<Value>),
    Object(Vec<(String, Value)>),
}

impl Value {
    pub fn get(&self, key: &str) -> Option<&Value> {
        match self {
            Value::Object(items) => items.iter().find(|(k, _)| k == key).map(|(_, v)| v),
            _ => None,
        }
    }

    pub fn as_str(&self) -> Option<&str> {
        match self {
            Value::Str(text) => Some(text),
            _ => None,
        }
    }

    /// A whole number, as Python's `int()` takes one: a float is cut to its whole part.
    pub fn as_int(&self) -> Option<i128> {
        match self {
            Value::Int(n) => Some(*n),
            Value::Float(f) if f.is_finite() => Some(f.trunc() as i128),
            Value::Bool(b) => Some(*b as i128),
            _ => None,
        }
    }

    pub fn as_list(&self) -> Option<&[Value]> {
        match self {
            Value::List(items) => Some(items),
            _ => None,
        }
    }

    pub fn write(&self, out: &mut String) {
        match self {
            Value::Null => out.push_str("null"),
            Value::Bool(true) => out.push_str("true"),
            Value::Bool(false) => out.push_str("false"),
            Value::Int(n) => {
                let _ = write!(out, "{n}");
            }
            Value::Float(f) if f.is_finite() => {
                let _ = write!(out, "{f:?}");
            }
            Value::Float(_) => out.push_str("null"),
            Value::Str(text) => write_str(text, out),
            Value::List(items) => {
                out.push('[');
                for (index, item) in items.iter().enumerate() {
                    if index > 0 {
                        out.push_str(", ");
                    }
                    item.write(out);
                }
                out.push(']');
            }
            Value::Object(items) => {
                out.push('{');
                for (index, (key, item)) in items.iter().enumerate() {
                    if index > 0 {
                        out.push_str(", ");
                    }
                    write_str(key, out);
                    out.push_str(": ");
                    item.write(out);
                }
                out.push('}');
            }
        }
    }

    pub fn to_json(&self) -> String {
        let mut out = String::new();
        self.write(&mut out);
        out
    }
}

/// An object from (key, value) pairs, in that order.
pub fn object<const N: usize>(items: [(&str, Value); N]) -> Value {
    Value::Object(items.into_iter().map(|(k, v)| (k.to_string(), v)).collect())
}

fn write_str(text: &str, out: &mut String) {
    out.push('"');
    for c in text.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => {
                let _ = write!(out, "\\u{:04x}", c as u32);
            }
            c => out.push(c),
        }
    }
    out.push('"');
}

pub fn parse(text: &[u8]) -> Result<Value, String> {
    let mut parser = Parser { text, at: 0 };
    let value = parser.value(0)?;
    parser.space();
    if parser.at != text.len() {
        return Err(format!("extra data at {}", parser.at));
    }
    Ok(value)
}

const DEEPEST: usize = 64; // nesting a request may have: they have two levels

struct Parser<'a> {
    text: &'a [u8],
    at: usize,
}

impl Parser<'_> {
    fn space(&mut self) {
        while let Some(b' ' | b'\t' | b'\n' | b'\r') = self.text.get(self.at) {
            self.at += 1;
        }
    }

    fn take(&mut self, word: &str, value: Value) -> Result<Value, String> {
        if self.text[self.at..].starts_with(word.as_bytes()) {
            self.at += word.len();
            Ok(value)
        } else {
            Err(format!("unexpected text at {}", self.at))
        }
    }

    fn value(&mut self, depth: usize) -> Result<Value, String> {
        if depth > DEEPEST {
            return Err("nested too deeply".into());
        }
        self.space();
        match self.text.get(self.at) {
            None => Err("unexpected end".into()),
            Some(b'n') => self.take("null", Value::Null),
            Some(b't') => self.take("true", Value::Bool(true)),
            Some(b'f') => self.take("false", Value::Bool(false)),
            Some(b'"') => Ok(Value::Str(self.string()?)),
            Some(b'[') => {
                self.at += 1;
                let mut items = Vec::new();
                self.space();
                if self.text.get(self.at) == Some(&b']') {
                    self.at += 1;
                    return Ok(Value::List(items));
                }
                loop {
                    items.push(self.value(depth + 1)?);
                    self.space();
                    match self.text.get(self.at) {
                        Some(b',') => self.at += 1,
                        Some(b']') => {
                            self.at += 1;
                            return Ok(Value::List(items));
                        }
                        _ => return Err(format!("expected , or ] at {}", self.at)),
                    }
                }
            }
            Some(b'{') => {
                self.at += 1;
                let mut items = Vec::new();
                self.space();
                if self.text.get(self.at) == Some(&b'}') {
                    self.at += 1;
                    return Ok(Value::Object(items));
                }
                loop {
                    self.space();
                    if self.text.get(self.at) != Some(&b'"') {
                        return Err(format!("expected a key at {}", self.at));
                    }
                    let key = self.string()?;
                    self.space();
                    if self.text.get(self.at) != Some(&b':') {
                        return Err(format!("expected : at {}", self.at));
                    }
                    self.at += 1;
                    items.push((key, self.value(depth + 1)?));
                    self.space();
                    match self.text.get(self.at) {
                        Some(b',') => self.at += 1,
                        Some(b'}') => {
                            self.at += 1;
                            return Ok(Value::Object(items));
                        }
                        _ => return Err(format!("expected , or }} at {}", self.at)),
                    }
                }
            }
            Some(b'-' | b'0'..=b'9') => self.number(),
            Some(_) => Err(format!("unexpected text at {}", self.at)),
        }
    }

    fn number(&mut self) -> Result<Value, String> {
        let start = self.at;
        let mut float = false;
        while let Some(&c) = self.text.get(self.at) {
            match c {
                b'0'..=b'9' | b'-' | b'+' => {}
                b'.' | b'e' | b'E' => float = true,
                _ => break,
            }
            self.at += 1;
        }
        let text = std::str::from_utf8(&self.text[start..self.at]).map_err(|e| e.to_string())?;
        if float {
            text.parse().map(Value::Float).map_err(|_| format!("bad number {text}"))
        } else {
            text.parse().map(Value::Int).map_err(|_| format!("bad number {text}"))
        }
    }

    fn string(&mut self) -> Result<String, String> {
        self.at += 1; // the opening quote
        let mut out = String::new();
        loop {
            let start = self.at;
            while let Some(&c) = self.text.get(self.at) {
                if c == b'"' || c == b'\\' {
                    break;
                }
                self.at += 1;
            }
            out.push_str(std::str::from_utf8(&self.text[start..self.at]).map_err(|e| e.to_string())?);
            match self.text.get(self.at) {
                None => return Err("unterminated string".into()),
                Some(b'"') => {
                    self.at += 1;
                    return Ok(out);
                }
                _ => {}
            }
            self.at += 1; // the backslash
            let escaped = *self.text.get(self.at).ok_or("unterminated string")?;
            self.at += 1;
            match escaped {
                b'"' => out.push('"'),
                b'\\' => out.push('\\'),
                b'/' => out.push('/'),
                b'b' => out.push('\u{8}'),
                b'f' => out.push('\u{c}'),
                b'n' => out.push('\n'),
                b'r' => out.push('\r'),
                b't' => out.push('\t'),
                b'u' => {
                    let mut unit = self.hex4()?;
                    if (0xD800..0xDC00).contains(&unit) && self.text[self.at..].starts_with(b"\\u") {
                        self.at += 2;
                        let low = self.hex4()?;
                        unit = 0x10000 + ((unit - 0xD800) << 10) + (low.wrapping_sub(0xDC00) & 0x3FF);
                    }
                    out.push(char::from_u32(unit).unwrap_or('\u{fffd}'));
                }
                _ => return Err(format!("bad escape at {}", self.at)),
            }
        }
    }

    fn hex4(&mut self) -> Result<u32, String> {
        let digits = self.text.get(self.at..self.at + 4).ok_or("short \\u escape")?;
        self.at += 4;
        u32::from_str_radix(std::str::from_utf8(digits).map_err(|e| e.to_string())?, 16)
            .map_err(|_| "bad \\u escape".to_string())
    }
}

/// Keys of an object, for tests and errors.
#[allow(dead_code)]
pub fn keys(value: &Value) -> BTreeMap<String, Value> {
    match value {
        Value::Object(items) => items.iter().cloned().collect(),
        _ => BTreeMap::new(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reads_a_request_as_python_writes_it() {
        let value = parse(br#"{"op": "search", "regions": [[65536, 131072]], "value": 1234605616436508552, "first": null}"#)
            .unwrap();
        assert_eq!(value.get("op").and_then(Value::as_str), Some("search"));
        assert_eq!(value.get("value").and_then(Value::as_int), Some(0x1122334455667788));
        let regions = value.get("regions").and_then(Value::as_list).unwrap();
        assert_eq!(regions[0].as_list().unwrap()[1].as_int(), Some(131072));
        assert_eq!(value.get("first"), Some(&Value::Null));
    }

    #[test]
    fn reads_strings_with_escapes() {
        let value = parse(br#"["a\"b\\c\n", "\u00e9\ud83d\ude00", "plain"]"#).unwrap();
        let items = value.as_list().unwrap();
        assert_eq!(items[0].as_str(), Some("a\"b\\c\n"));
        assert_eq!(items[1].as_str(), Some("é😀"));
    }

    #[test]
    fn refuses_what_is_not_json() {
        assert!(parse(b"{\"op\": }").is_err());
        assert!(parse(b"[1, 2").is_err());
        assert!(parse(b"{} x").is_err());
        assert!(parse(&[b'['; 100]).is_err());
    }

    #[test]
    fn writes_what_python_reads() {
        let value = object([
            ("ok", Value::Bool(true)),
            ("got", Value::List(vec![Value::Int(16), Value::Int(19)])),
            ("took", Value::Float(0.25)),
            ("path", Value::Str("C:\\x \"y\"\u{1}".into())),
            ("hit", Value::Null),
        ]);
        assert_eq!(
            value.to_json(),
            r#"{"ok": true, "got": [16, 19], "took": 0.25, "path": "C:\\x \"y\"\u0001", "hit": null}"#
        );
        assert_eq!(parse(value.to_json().as_bytes()).unwrap(), value);
    }

    #[test]
    fn a_float_cuts_to_a_whole_number() {
        assert_eq!(parse(b"3.9").unwrap().as_int(), Some(3));
        assert_eq!(parse(b"-7").unwrap().as_int(), Some(-7));
    }
}
