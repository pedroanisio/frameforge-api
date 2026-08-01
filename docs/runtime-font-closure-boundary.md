# Runtime font-closure boundary

FrameForge documents declare which font identity they intend to use; a render
invocation declares which portable set of font bytes is available for that
run. These are deliberately separate contracts.

## Ownership

| Concern | Owner | Public surface |
|---|---|---|
| Family, face source, content pin | `frameforge-api` | `FontDef.family`, `FontDef.src`, `FontDef.hash`, weight/style/fallback |
| Closure import, shaping, face selection | `frameforge-fonts` | `closure_provider()` |
| Author-time measure/wrap/height | `frameforge-sdk` | `closure_metrics()` and `metrics_provider=` |
| Render-time text fitting | `frameforge-render` / `frameforge.conform` | `metrics_provider=` |
| Agent invocation | `frameforge-mcp` | `font_closure=` and `font_generics=` |

`font_closure` and `font_generics` therefore are not fields on `Document` and
do not appear in the generated JSON Schema. Serializing a host or session path
into a document would make the document machine-specific and confuse runtime
availability with document intent.

## End-to-end use

The document pins a face using the existing API:

```json
{
  "defs": {
    "tokens": {
      "fonts": {
        "body": {
          "family": "Pinned Sans",
          "src": "fonts/pinned-sans.woff2",
          "hash": "sha256:<64 hex characters>",
          "weight": 400
        }
      }
    }
  }
}
```

The caller supplies the closure when measuring or rendering:

```python
from frameforge_sdk import closure_metrics, measure_text

provider = closure_metrics(
    "fonts.fp",
    strict=True,
    generics={"sans-serif": "Pinned Sans"},
)
width = measure_text(
    "Portable",
    font_family="Pinned Sans",
    font_size=12,
    metrics_provider=provider,
)
```

For MCP render and `fit_text` calls, pass `font_closure: "/path/fonts.fp"`
and, when the document uses CSS generics, `font_generics:
{"sans-serif": "Pinned Sans"}`. Closure paths obey
`FRAMEFORGE_MCP_INPUT_ROOTS`; the result reports the closure SHA-256 and
`metrics_mode: "closure"`.

## Migration guidance

If an integration stored a closure path in `meta`, keep that data only for
round-trip compatibility and move the path to the SDK/render/MCP invocation.
Do not introduce a `Document.font_closure` field. No document-version bump or
schema migration is required for this capability.
