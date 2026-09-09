//! Native resource decoding. Python retains catalog headers, models and custom decoders.

use std::collections::{HashMap, HashSet};

use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList, PyString, PyType};
use pyo3::IntoPyObjectExt;

const NULL: u32 = u32::MAX;

#[derive(Clone, Copy)]
enum Kind {
    Int,
    Long,
    Bool,
    String,
    Hash,
    Bundle,
    Unsupported,
}

struct Parser<'py, 'data> {
    py: Python<'py>,
    data: &'data [u8],
    version: u32,
    objects: HashMap<u32, Py<PyAny>>,
    shared_objects: Option<Bound<'py, PyDict>>,
    object_decoder: Option<Bound<'py, PyAny>>,
    strings: HashMap<(u32, u8), Py<PyAny>>,
    kinds: HashMap<u32, (Kind, String)>,
    location_class: Bound<'py, PyAny>,
    type_class: Bound<'py, PyAny>,
    hash_class: Bound<'py, PyAny>,
    bundle_class: Bound<'py, PyAny>,
    common_class: Bound<'py, PyAny>,
    load_mode_class: Bound<'py, PyAny>,
    read_error: Bound<'py, PyType>,
    unsupported_error: Bound<'py, PyType>,
}

impl<'py, 'data> Parser<'py, 'data> {
    fn new(
        py: Python<'py>,
        data: &'data [u8],
        version: u32,
        cached: &Bound<'py, PyDict>,
        object_decoder: Option<Bound<'py, PyAny>>,
    ) -> PyResult<Self> {
        let models = py.import("addressablestools.models")?;
        let errors = py.import("addressablestools.exceptions")?;
        let mut objects = HashMap::new();
        if object_decoder.is_none() {
            for (key, value) in cached.iter() {
                objects.insert(key.extract()?, value.unbind());
            }
        }
        Ok(Self {
            py,
            data,
            version,
            objects,
            shared_objects: object_decoder.as_ref().map(|_| cached.clone()),
            object_decoder,
            strings: HashMap::new(),
            kinds: HashMap::new(),
            location_class: models.getattr("ResourceLocation")?,
            type_class: models.getattr("SerializedType")?,
            hash_class: models.getattr("Hash128")?,
            bundle_class: models.getattr("AssetBundleRequestOptions")?,
            common_class: models.getattr("CommonInfo")?,
            load_mode_class: models.getattr("AssetLoadMode")?,
            read_error: errors.getattr("BinaryReadError")?.cast_into()?,
            unsupported_error: errors
                .getattr("UnsupportedSerializedObjectError")?
                .cast_into()?,
        })
    }

    fn invalid(&self, message: impl Into<String>) -> PyErr {
        PyErr::from_type(self.read_error.clone(), (message.into(),))
    }

    fn cached(&self, offset: u32) -> PyResult<Option<Py<PyAny>>> {
        if let Some(objects) = &self.shared_objects {
            return Ok(objects
                .get_item(offset)?
                .filter(|v| !v.is_none())
                .map(Bound::unbind));
        }
        Ok(self
            .objects
            .get(&offset)
            .map(|value| value.clone_ref(self.py)))
    }

    fn cache(&mut self, offset: u32, value: &Py<PyAny>) -> PyResult<()> {
        if let Some(objects) = &self.shared_objects {
            objects.set_item(offset, value)?;
        } else {
            self.objects.insert(offset, value.clone_ref(self.py));
        }
        Ok(())
    }

    fn is_cached(&self, offset: u32) -> PyResult<bool> {
        if self.shared_objects.is_some() {
            return Ok(self.cached(offset)?.is_some());
        }
        Ok(self.objects.contains_key(&offset))
    }

    fn bytes(&self, offset: u32, count: usize) -> PyResult<&'data [u8]> {
        let start = offset as usize;
        let end = start
            .checked_add(count)
            .ok_or_else(|| self.invalid("offset overflow"))?;
        self.data.get(start..end).ok_or_else(|| {
            self.invalid(format!("data is truncated: expected {count} bytes at position {offset}, buffer has {} bytes", self.data.len()))
        })
    }

    fn word(&self, offset: u32) -> PyResult<u32> {
        Ok(word(self.bytes(offset, 4)?))
    }

    fn length(&self, offset: u32) -> PyResult<usize> {
        let prefix = offset
            .checked_sub(4)
            .ok_or_else(|| self.invalid("invalid length prefix offset"))?;
        let size = self.word(prefix)? as i32;
        if size < 0 {
            return Err(self.invalid("byte size must be non-negative"));
        }
        Ok(size as usize)
    }

    fn array(&self, offset: u32) -> PyResult<&'data [u8]> {
        if offset == NULL {
            return Ok(&[]);
        }
        let size = self.length(offset)?;
        if size % 4 != 0 {
            return Err(self.invalid("offset array byte size must be a multiple of 4"));
        }
        self.bytes(offset, size)
    }

    fn string(&mut self, encoded: u32, separator: u8) -> PyResult<Py<PyAny>> {
        if encoded == NULL || encoded == NULL - 1 {
            return Ok(self.py.None());
        }
        let dynamic = encoded & 0x4000_0000 != 0 && separator != 0;
        let key = (encoded, if dynamic { separator } else { 0 });
        if let Some(value) = self.strings.get(&key) {
            return Ok(value.clone_ref(self.py));
        }
        let offset = encoded & 0x3fff_ffff;
        let value = if dynamic {
            let first_record = self.bytes(offset, 8)?;
            if word(&first_record[4..]) == NULL {
                let first = self.string(word(first_record), 0)?;
                let value = if first.is_none(self.py) {
                    PyString::new(self.py, "").into_any().unbind()
                } else {
                    first
                };
                self.strings.insert(key, value.clone_ref(self.py));
                return Ok(value);
            }
            let mut next = offset;
            let mut visited = HashSet::new();
            let mut parts = Vec::new();
            loop {
                if !visited.insert(next) {
                    return Err(self.invalid(format!(
                        "dynamic string part chain contains a cycle at offset {next}"
                    )));
                }
                let record = self.bytes(next, 8)?;
                let part = self.string(word(record), 0)?;
                if !part.is_none(self.py) {
                    parts.push(part);
                }
                next = word(&record[4..]);
                if next == NULL {
                    break;
                }
            }
            if self.version > 1 {
                parts.reverse();
            }
            // Retain shared fragments instead of copying their text into Rust Strings.
            PyString::new(self.py, &char::from(separator).to_string())
                .call_method1("join", (PyList::new(self.py, parts)?,))?
                .unbind()
        } else {
            let raw = self.bytes(offset, self.length(offset)?)?;
            if encoded & 0x8000_0000 != 0 {
                // Delegate codec edge cases to CPython to preserve UnicodeDecodeError details.
                PyBytes::new(self.py, raw)
                    .call_method1("decode", ("utf-16-le",))?
                    .unbind()
            } else if raw.is_ascii() {
                let text = std::str::from_utf8(raw).expect("ASCII is valid UTF-8");
                PyString::new(self.py, text).into_any().unbind()
            } else {
                PyBytes::new(self.py, raw)
                    .call_method1("decode", ("ascii",))?
                    .unbind()
            }
        };
        self.strings.insert(key, value.clone_ref(self.py));
        Ok(value)
    }

    fn serialized_type(&mut self, offset: u32) -> PyResult<Py<PyAny>> {
        if let Some(value) = self.cached(offset)? {
            return Ok(value);
        }
        let record = self.bytes(offset, 8)?;
        let assembly = self.string(word(record), b'.')?;
        let class = self.string(word(&record[4..]), b'.')?;
        let value = self.type_class.call1((assembly, class))?.unbind();
        self.cache(offset, &value)?;
        Ok(value)
    }

    fn object(&mut self, offset: u32) -> PyResult<(Py<PyAny>, Py<PyAny>)> {
        if offset == NULL {
            return Ok((self.py.None(), self.py.None()));
        }
        // Keep live registry resolution and callback semantics in the reference decoder.
        // The shared object cache preserves identity across Python and Rust traversal.
        if let Some(decoder) = &self.object_decoder {
            return decoder.call1((offset,))?.extract();
        }
        let record = self.bytes(offset, 8)?;
        let type_offset = word(record);
        let payload = word(&record[4..]);
        let serialized_type = self.serialized_type(type_offset)?;
        if !self.kinds.contains_key(&type_offset) {
            let name: String = serialized_type
                .bind(self.py)
                .call_method1("match_name_for_version", (self.version,))?
                .extract()?;
            let kind = match name.as_str() {
                "mscorlib; System.Int32" | "System.Int32" => Kind::Int,
                "mscorlib; System.Int64" | "System.Int64" => Kind::Long,
                "mscorlib; System.Boolean" | "System.Boolean" => Kind::Bool,
                "mscorlib; System.String" | "System.String" => Kind::String,
                "UnityEngine.CoreModule; UnityEngine.Hash128" => Kind::Hash,
                "Unity.ResourceManager; UnityEngine.ResourceManagement.ResourceProviders.AssetBundleRequestOptions" => Kind::Bundle,
                _ => Kind::Unsupported,
            };
            self.kinds.insert(type_offset, (kind, name));
        }
        let kind = self.kinds[&type_offset].0;
        let value = match kind {
            Kind::Int => {
                let value = if payload == NULL {
                    0
                } else {
                    self.word(payload)? as i32
                };
                value.into_py_any(self.py)?
            }
            Kind::Long => {
                let value = if payload == NULL {
                    0
                } else {
                    i64::from_le_bytes(self.bytes(payload, 8)?.try_into().expect("eight bytes"))
                };
                value.into_py_any(self.py)?
            }
            Kind::Bool => {
                let value = payload != NULL && self.bytes(payload, 1)?[0] != 0;
                value.into_py_any(self.py)?
            }
            Kind::String if payload != NULL => {
                let record = self.bytes(payload, 5)?;
                self.string(word(record), record[4])?
            }
            Kind::Hash if payload != NULL => {
                let value = hex(self.bytes(payload, 16)?);
                self.hash_class.call1((value,))?.unbind()
            }
            Kind::Bundle if payload != NULL => self.bundle(payload)?,
            Kind::Unsupported => {
                return Err(PyErr::from_type(
                    self.unsupported_error.clone(),
                    (format!(
                        "Unsupported object type: {}",
                        self.kinds[&type_offset].1
                    ),),
                ));
            }
            _ => self.py.None(),
        };
        Ok((value, serialized_type))
    }

    fn common(&mut self, offset: u32) -> PyResult<Py<PyAny>> {
        if let Some(value) = self.cached(offset)? {
            return Ok(value);
        }
        let data = self.bytes(offset, 8)?;
        let timeout = i16::from_le_bytes([data[0], data[1]]);
        let flags = word(&data[4..]);
        let mode = self.load_mode_class.call1((flags & 1,))?;
        let value = self
            .common_class
            .call1((
                timeout,
                data[2],
                data[3],
                mode,
                flags & 2 != 0,
                flags & 4 != 0,
                flags & 8 != 0,
                flags & 16 != 0,
                3,
            ))?
            .unbind();
        self.cache(offset, &value)?;
        Ok(value)
    }

    fn bundle(&mut self, offset: u32) -> PyResult<Py<PyAny>> {
        if let Some(value) = self.cached(offset)? {
            return Ok(value);
        }
        let data = self.bytes(offset, 20)?;
        let hash = hex(self.bytes(word(data), 16)?);
        let common = self.common(word(&data[16..]))?;
        let name = self.string(word(&data[4..]), b'_')?;
        let value = self
            .bundle_class
            .call1((hash, word(&data[8..]), common, name, word(&data[12..])))?
            .unbind();
        self.cache(offset, &value)?;
        Ok(value)
    }

    fn location(&mut self, root: u32) -> PyResult<Py<PyAny>> {
        if let Some(value) = self.cached(root)? {
            return Ok(value);
        }
        let record = self.bytes(root, 28)?;
        let mut ready = true;
        for entry in self.array(word(&record[12..]))?.chunks_exact(4) {
            if !self.is_cached(word(entry))? {
                ready = false;
                break;
            }
        }
        if ready {
            return self.build_location(root);
        }
        // Iterative postorder avoids consuming the native stack on deep dependency graphs.
        let mut pending = vec![(root, false)];
        let mut active = HashSet::new();
        while let Some((offset, expanded)) = pending.pop() {
            if self.is_cached(offset)? {
                continue;
            }
            let record = self.bytes(offset, 28)?;
            let dependencies = self.array(word(&record[12..]))?;
            if !expanded {
                if !active.insert(offset) {
                    return Err(self.invalid(format!(
                        "resource dependency graph contains a cycle at offset {offset}"
                    )));
                }
                pending.push((offset, true));
                for entry in dependencies.chunks_exact(4).rev() {
                    let child = word(entry);
                    if !self.is_cached(child)? {
                        pending.push((child, false));
                    }
                }
                continue;
            }
            self.build_location(offset)?;
            active.remove(&offset);
        }
        self.cached(root)?
            .ok_or_else(|| self.invalid("missing decoded resource"))
    }

    fn build_location(&mut self, offset: u32) -> PyResult<Py<PyAny>> {
        let record = self.bytes(offset, 28)?;
        let primary = self.string(word(record), b'/')?;
        let internal = self.string(word(&record[4..]), b'/')?;
        let provider = self.string(word(&record[8..]), b'.')?;
        let dependency_list = if self.shared_objects.is_none() {
            PyList::new(
                self.py,
                self.array(word(&record[12..]))?
                    .chunks_exact(4)
                    .map(|entry| self.objects[&word(entry)].bind(self.py)),
            )?
        } else {
            PyList::new(
                self.py,
                self.array(word(&record[12..]))?
                    .chunks_exact(4)
                    .map(|entry| {
                        self.cached(word(entry))?
                            .ok_or_else(|| self.invalid("missing decoded dependency"))
                    })
                    .collect::<PyResult<Vec<_>>>()?,
            )?
        };
        let (data, data_type) = self.object(word(&record[20..]))?;
        let resource_type = self.serialized_type(word(&record[24..]))?;
        let hash =
            internal.bind(self.py).hash()? as i128 * 31 + provider.bind(self.py).hash()? as i128;
        let value = self
            .location_class
            .call1((
                internal,
                provider,
                self.py.None(),
                dependency_list,
                data,
                hash,
                word(&record[16..]) as i32,
                primary,
                resource_type,
            ))?
            .unbind();
        value.bind(self.py).setattr("_data_type", data_type)?;
        self.cache(offset, &value)?;
        Ok(value)
    }

    fn resources(&mut self, offset: u32) -> PyResult<Py<PyDict>> {
        let keys = self.array(offset)?;
        if keys.len() % 8 != 0 {
            return Err(self.invalid("key/location offset array must contain pairs"));
        }
        let result = PyDict::new(self.py);
        for pair in keys.chunks_exact(8) {
            let (key, _) = self.object(word(pair))?;
            let offsets = self.array(word(&pair[4..]))?;
            let locations = if offsets.len() == 4 {
                PyList::new(self.py, [self.location(word(offsets))?])?
            } else {
                let values = offsets
                    .chunks_exact(4)
                    .map(|entry| self.location(word(entry)))
                    .collect::<PyResult<Vec<_>>>()?;
                PyList::new(self.py, values)?
            };
            result.set_item(key, locations)?;
        }
        Ok(result.unbind())
    }
}

fn word(bytes: &[u8]) -> u32 {
    u32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]])
}

fn hex(bytes: &[u8]) -> String {
    const DIGITS: &[u8; 16] = b"0123456789abcdef";
    let mut result = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        result.push(DIGITS[(byte >> 4) as usize] as char);
        result.push(DIGITS[(byte & 15) as usize] as char);
    }
    result
}

#[pyfunction]
pub fn decode_resources(
    py: Python<'_>,
    data: &[u8],
    version: u32,
    keys_offset: u32,
    cached: &Bound<'_, PyDict>,
) -> PyResult<Py<PyDict>> {
    Parser::new(py, data, version, cached, None)?.resources(keys_offset)
}

#[pyfunction]
pub fn decode_resources_with_registry<'py>(
    py: Python<'py>,
    data: &[u8],
    version: u32,
    keys_offset: u32,
    cached: &Bound<'py, PyDict>,
    object_decoder: Bound<'py, PyAny>,
) -> PyResult<Py<PyDict>> {
    Parser::new(py, data, version, cached, Some(object_decoder))?.resources(keys_offset)
}
