# Multilingual Huffman codec foundation

`multilang_codec` builds deterministic, explicit-table FE8 Huffman catalogs
without selecting a locale or emitting C. Message bytes are opaque: UTF-8 and
FE control bytes are preserved, not validated. Every present message must have
one trailing NUL and no interior NUL.

The serialized model uses:

- `0xFFFF0000 | symbol` leaves;
- `(right_index << 16) | left_index` internal nodes;
- LSB-first, independently byte-aligned message streams whose exact meaningful
  bit lengths exclude zero padding;
- blob-relative pointer offsets, byte storage sizes, and meaningful bit lengths;
- `present: false` plus `pointer_offset: null` for an absent entry, allowing a
  future runtime catalog resolver to choose English fallback before decoding;
- deterministic budget and SHA-256 round-trip metadata.

`build_catalog(messages, suffix_share=True)` optionally reuses a strictly
shorter compressed byte suffix of the immediate predecessor. No global
deduplication is performed.

The C decoder in `include/localized_text_codec.h` is table-independent and is
compiled only for modern profiles whose generated locale mask enables Japanese
or Simplified Chinese. Legacy and default English-only profiles emit no codec
declarations or implementation. The decoder requires a terminating NUL within
the exact meaningful bit length; byte padding is never consumed. Its decoded
length includes the terminating NUL; on failure it is the number of bytes
safely written before the failure.

Run the focused Python and host-native C tests from the repository root:

```sh
python3 -m unittest discover -s scripts/texttools/tests \
    -p 'test_multilang_codec*.py' -v
```

The native test uses host `cc`, compiles the real C implementation as strict
C89, writes scratch artifacts only below `scripts/texttools/tests/`, and removes
them before exit.
