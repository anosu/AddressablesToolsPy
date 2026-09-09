//! Optional resource decoding backends sharing the public Python model types.

mod binary;
mod json;

use pyo3::prelude::*;

#[pymodule]
fn _addressablestools_rust(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("API_VERSION", 3)?;
    module.add("__version__", env!("CARGO_PKG_VERSION"))?;
    module.add_function(wrap_pyfunction!(binary::decode_resources, module)?)?;
    module.add_function(wrap_pyfunction!(
        binary::decode_resources_with_registry,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(json::decode_json_resources, module)?)?;
    Ok(())
}
