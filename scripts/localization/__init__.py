"""Expansion framework localization platform (issue #18 sprint 1).

Pure-stdlib tools that own the canonical message registry/catalog under
texts/expansion/, the stable ExpansionLocaleId/ExpansionMsgId identifier
contract shared with include/expansion_locale.h, and the deterministic
generator that produces the C header/source/budget report consumed by the
modern linked build (see modern.mk's "Localization catalog" section).

Deliberately independent of the vanilla texts/texts.txt -> src/msg_data.c /
include/constants/msg.h pipeline, GetLang()/SetLang()/gLanguageMode, and
XMAP: nothing here reads, decodes, or transforms any vanilla/foreign
original-game text. Every string this package ships is new expansion
framework English (plus an ASCII pseudo-locale transform of that same
English), never vanilla dialogue.
"""
