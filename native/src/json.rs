//! JSON's embedded tables are decoded natively; Python retains text/metadata semantics.

use std::ops::Range;

use base64::Engine;
use pyo3::exceptions::{PyKeyError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList, PyString, PyType};
use pyo3::IntoPyObjectExt;

struct Bucket {
    key: usize,
    entries: Range<usize>,
}

struct Parser<'py> {
    py: Python<'py>,
    error: Bound<'py, PyType>,
    read_error: Bound<'py, PyType>,
    location_class: Bound<'py, PyAny>,
    hash_class: Bound<'py, PyAny>,
    reference_class: Bound<'py, PyAny>,
    type_class: Bound<'py, PyAny>,
    json_class: Bound<'py, PyAny>,
    object_kind: Bound<'py, PyAny>,
    decode_options: Bound<'py, PyAny>,
    expand_id: Bound<'py, PyAny>,
}

impl<'py> Parser<'py> {
    fn new(py: Python<'py>) -> PyResult<Self> {
        let models = py.import("addressablestools.models")?;
        let errors = py.import("addressablestools.exceptions")?;
        let decoder = py
            .import("addressablestools.decoder")?
            .getattr("SerializedObjectDecoder")?;
        Ok(Self {
            py,
            error: errors.getattr("CatalogParseError")?.cast_into()?,
            read_error: errors.getattr("BinaryReadError")?.cast_into()?,
            location_class: models.getattr("ResourceLocation")?,
            hash_class: models.getattr("Hash128")?,
            reference_class: models.getattr("TypeReference")?,
            type_class: models.getattr("SerializedType")?,
            json_class: models.getattr("ClassJsonObject")?,
            object_kind: decoder.getattr("ObjectType")?,
            decode_options: decoder.getattr("decode_asset_bundle_request_options_json")?,
            expand_id: py
                .import("addressablestools.catalog")?
                .getattr("_apply_internal_id_prefix")?,
        })
    }

    fn invalid(&self, message: impl Into<String>) -> PyErr {
        PyErr::from_type(self.error.clone(), (message.into(),))
    }

    fn bytes<'a>(&self, data: &'a [u8], offset: usize, count: usize) -> PyResult<&'a [u8]> {
        offset
            .checked_add(count)
            .and_then(|end| data.get(offset..end))
            .ok_or_else(|| self.invalid("invalid catalog JSON data: embedded table is truncated"))
    }

    fn read_bytes<'a>(&self, data: &'a [u8], offset: usize, count: usize) -> PyResult<&'a [u8]> {
        offset
            .checked_add(count)
            .and_then(|end| data.get(offset..end))
            .ok_or_else(|| {
                PyErr::from_type(
                    self.read_error.clone(),
                    (format!("expected {count} bytes at position {offset}"),),
                )
            })
    }

    fn index(&self, index: i32, count: usize, name: &str) -> PyResult<usize> {
        if index < 0 || index as usize >= count {
            return Err(self.invalid(format!("{name} index {index} is out of range")));
        }
        Ok(index as usize)
    }

    fn text(&self, data: &[u8], unicode: bool) -> PyResult<Py<PyAny>> {
        if !unicode && data.is_ascii() {
            let text = std::str::from_utf8(data).expect("ASCII is valid UTF-8");
            Ok(PyString::new(self.py, text).into_any().unbind())
        } else {
            Ok(PyBytes::new(self.py, data)
                .call_method1("decode", (if unicode { "utf-16-le" } else { "ascii" },))?
                .unbind())
        }
    }

    fn key(&self, data: &[u8], offset: usize) -> PyResult<Py<PyAny>> {
        let kind = self.bytes(data, offset, 1)?[0];
        match kind {
            0 | 1 => {
                let size = word(self.bytes(data, offset + 1, 4)?);
                if size < 0 {
                    return Err(self.invalid("key string byte length must be non-negative"));
                }
                self.text(self.bytes(data, offset + 5, size as usize)?, kind == 1)
            }
            _ => Ok(self.object(data, offset)?.0),
        }
    }

    fn short_string(&self, data: &[u8], cursor: &mut usize) -> PyResult<Py<PyAny>> {
        let size = self.read_bytes(data, *cursor, 1)?[0] as usize;
        let result = self.text(self.read_bytes(data, *cursor + 1, size)?, false)?;
        *cursor += 1 + size;
        Ok(result)
    }

    fn long_string(&self, data: &[u8], cursor: usize, unicode: bool) -> PyResult<Py<PyAny>> {
        let size = word(self.read_bytes(data, cursor, 4)?);
        if size < 0 {
            return Err(PyErr::from_type(
                self.read_error.clone(),
                ("read byte count must be non-negative",),
            ));
        }
        self.text(self.read_bytes(data, cursor + 4, size as usize)?, unicode)
    }

    fn object(&self, data: &[u8], offset: usize) -> PyResult<(Py<PyAny>, Py<PyAny>)> {
        let kind = self.read_bytes(data, offset, 1)?[0];
        let value = match kind {
            0 | 1 => self.long_string(data, offset + 1, kind == 1)?,
            2 => {
                let raw = self.read_bytes(data, offset + 1, 2)?;
                u16::from_le_bytes([raw[0], raw[1]]).into_py_any(self.py)?
            }
            3 => (word(self.read_bytes(data, offset + 1, 4)?) as u32).into_py_any(self.py)?,
            4 => word(self.read_bytes(data, offset + 1, 4)?).into_py_any(self.py)?,
            5 | 6 => {
                let value = self.short_string(data, &mut (offset + 1))?;
                let class = if kind == 5 {
                    &self.hash_class
                } else {
                    &self.reference_class
                };
                class.call1((value,))?.unbind()
            }
            7 => {
                let mut cursor = offset + 1;
                let assembly = self.short_string(data, &mut cursor)?;
                let name = self.short_string(data, &mut cursor)?;
                let text = self.long_string(data, cursor, true)?;
                let serialized_type = self
                    .type_class
                    .call1((assembly.bind(self.py), name.bind(self.py)))?
                    .unbind();
                let assembly_text = assembly.bind(self.py).cast::<PyString>()?.to_str()?;
                let class_text = name.bind(self.py).cast::<PyString>()?.to_str()?;
                let value = if assembly_text.split(',').next() == Some("Unity.ResourceManager")
                    && class_text == "UnityEngine.ResourceManagement.ResourceProviders.AssetBundleRequestOptions" {
                    // Keep all historical field defaults/conversions and json.loads semantics.
                    self.decode_options.call1((text,))?.unbind()
                } else {
                    self.json_class.call1((serialized_type.bind(self.py), text))?.unbind()
                };
                return Ok((value, serialized_type));
            }
            _ => {
                self.object_kind.call1((kind,))?;
                return Err(self.invalid("unsupported serialized object type"));
            }
        };
        Ok((value, self.py.None()))
    }

    fn resources(
        &self,
        catalog: &Bound<'py, PyAny>,
        raw: &Bound<'py, PyDict>,
    ) -> PyResult<Py<PyDict>> {
        let bucket_blob = blob(self.py, raw, "m_BucketDataString")?;
        let bucket_data = bucket_blob.as_bytes();
        let count = word(self.bytes(bucket_data, 0, 4)?);
        if count < 0 {
            return Err(self.invalid("bucket count must be non-negative"));
        }
        // Validate before reserving memory from an untrusted count.
        if count as usize > (bucket_data.len() - 4) / 8 {
            return Err(self.invalid("bucket data is truncated"));
        }
        let mut buckets = Vec::with_capacity(count as usize);
        let mut cursor = 4;
        for _ in 0..count {
            let header = self.bytes(bucket_data, cursor, 8)?;
            let key = word(header);
            let entries = word(&header[4..]);
            if key < 0 {
                return Err(self.invalid("bucket key offset must be non-negative"));
            }
            if entries < 0 {
                return Err(self.invalid("bucket entry count must be non-negative"));
            }
            cursor += 8;
            let size = (entries as usize)
                .checked_mul(4)
                .ok_or_else(|| self.invalid("bucket size overflow"))?;
            self.bytes(bucket_data, cursor, size)?;
            buckets.push(Bucket {
                key: key as usize,
                entries: cursor..cursor + size,
            });
            cursor += size;
        }

        let key_blob = blob(self.py, raw, "m_KeyDataString")?;
        let key_data = key_blob.as_bytes();
        let key_count = word(self.read_bytes(key_data, 0, 4)?);
        if key_count < 0 {
            return Err(self.invalid("key count must be non-negative"));
        }
        if key_count != count {
            return Err(self.invalid(format!(
                "key count {key_count} does not match bucket count {count}"
            )));
        }
        let mut keys = Vec::with_capacity(buckets.len());
        for bucket in &buckets {
            keys.push(self.key(key_data, bucket.key)?);
        }
        drop(key_blob);

        let entry_blob = blob(self.py, raw, "m_EntryDataString")?;
        let extra_blob = blob(self.py, raw, "m_ExtraDataString")?;
        let entry_data = entry_blob.as_bytes();
        let entry_count = word(self.bytes(entry_data, 0, 4)?);
        if entry_count < 0 {
            return Err(self.invalid("resource location count must be non-negative"));
        }
        let size = (entry_count as usize)
            .checked_mul(28)
            .ok_or_else(|| self.invalid("location size overflow"))?;
        let records = self.bytes(entry_data, 4, size)?;
        let mut internal_ids: Vec<Py<PyAny>> = catalog.getattr("internal_ids")?.extract()?;
        let prefixes = catalog.getattr("internal_id_prefixes")?;
        if prefixes.len()? != 0 {
            for value in &mut internal_ids {
                *value = self
                    .expand_id
                    .call1((value.bind(self.py), &prefixes))?
                    .unbind();
            }
        }
        let providers: Vec<Py<PyAny>> = catalog.getattr("provider_ids")?.extract()?;
        let hashes: Vec<isize> = providers
            .iter()
            .map(|value| value.bind(self.py).hash())
            .collect::<PyResult<_>>()?;
        let types: Vec<Py<PyAny>> = catalog.getattr("resource_types")?.extract()?;
        let primary_override: Option<Vec<Py<PyAny>>> = catalog.getattr("keys")?.extract()?;
        let primary_keys = primary_override.as_ref().unwrap_or(&keys);
        let mut locations = Vec::with_capacity(entry_count as usize);
        for record in records.chunks_exact(28) {
            let internal = self.index(word(record), internal_ids.len(), "internal ID")?;
            let provider = self.index(word(&record[4..]), providers.len(), "provider ID")?;
            let dependency = word(&record[8..]);
            let dependency_key = if dependency < 0 {
                self.py.None()
            } else {
                keys[self.index(dependency, keys.len(), "dependency key")?].clone_ref(self.py)
            };
            let primary = self.index(word(&record[20..]), primary_keys.len(), "primary key")?;
            let resource_type = self.index(word(&record[24..]), types.len(), "resource type")?;
            let extra = word(&record[16..]);
            let (data, data_type): (Py<PyAny>, Py<PyAny>) = if extra < 0 {
                (self.py.None(), self.py.None())
            } else {
                self.object(extra_blob.as_bytes(), extra as usize)?
            };
            let internal_id = internal_ids[internal].bind(self.py);
            let provider_id = providers[provider].bind(self.py);
            let hash = internal_id.hash()? as i128 * 31 + hashes[provider] as i128;
            let value = self.location_class.call1((
                internal_id,
                provider_id,
                dependency_key,
                self.py.None(),
                data,
                hash,
                word(&record[12..]),
                primary_keys[primary].bind(self.py).str()?,
                types[resource_type].bind(self.py),
            ))?;
            value.setattr("_data_type", data_type)?;
            locations.push(value.unbind());
        }
        // The reference parser releases these tables before building the final key map.
        // Do the same explicitly: Rust locals otherwise live until this function returns.
        drop(entry_blob);
        drop(extra_blob);
        drop(internal_ids);
        drop(providers);
        drop(hashes);
        drop(types);
        drop(primary_override);
        let result = PyDict::new(self.py);
        for (key, bucket) in keys.iter().zip(&buckets) {
            let entries = &bucket_data[bucket.entries.clone()];
            for entry in entries.chunks_exact(4) {
                self.index(word(entry), locations.len(), "bucket resource location")?;
            }
            let values = PyList::new(
                self.py,
                entries
                    .chunks_exact(4)
                    .map(|entry| locations[word(entry) as usize].bind(self.py)),
            )?;
            result.set_item(key, values)?;
        }
        Ok(result.unbind())
    }
}

fn word(data: &[u8]) -> i32 {
    i32::from_le_bytes([data[0], data[1], data[2], data[3]])
}

fn blob<'py>(
    py: Python<'py>,
    raw: &Bound<'py, PyDict>,
    name: &str,
) -> PyResult<Bound<'py, PyBytes>> {
    let text = raw
        .get_item(name)?
        .ok_or_else(|| PyKeyError::new_err(name.to_owned()))?
        .str()?;
    if let Ok(text) = text.to_str() {
        let padding = text
            .as_bytes()
            .iter()
            .rev()
            .take_while(|&&byte| byte == b'=')
            .count();
        if text.len() % 4 == 0 && padding <= 2 {
            let size = text.len() / 4 * 3 - padding;
            // Decode directly into the Python-owned buffer instead of retaining a Vec copy.
            let decoded =
                PyBytes::new_with(
                    py,
                    size,
                    |buffer| match base64::engine::general_purpose::STANDARD
                        .decode_slice(text, buffer)
                    {
                        Ok(written) if written == size => Ok(()),
                        _ => Err(PyValueError::new_err("noncanonical Base64")),
                    },
                );
            match decoded {
                Ok(bytes) => return Ok(bytes),
                Err(error) if error.is_instance_of::<PyValueError>(py) => {}
                Err(error) => return Err(error),
            }
        }
    }
    // Python accepts whitespace and some noncanonical padding. Preserve that behavior.
    Ok(py
        .import("base64")?
        .getattr("b64decode")?
        .call1((text,))?
        .cast_into()?)
}

#[pyfunction]
pub fn decode_json_resources(
    py: Python<'_>,
    catalog: &Bound<'_, PyAny>,
    raw: &Bound<'_, PyDict>,
) -> PyResult<Py<PyDict>> {
    Parser::new(py)?.resources(catalog, raw)
}
