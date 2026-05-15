import hashlib

from scripts.prompt_registry import (
    PromptRegistryEntry,
    iter_prompt_registry,
    validate_prompt_registry,
)


def test_prompt_registry_covers_model_backed_extractors():
    entries = iter_prompt_registry()
    prompt_ids = {entry.prompt_id for entry in entries}

    assert len(entries) == 9
    assert "opendatasheet.electrical.vision" in prompt_ids
    assert "opendatasheet.pin.standard" in prompt_ids
    assert "opendatasheet.pin.fpga" in prompt_ids
    assert "opendatasheet.design_guide.vision" in prompt_ids
    assert validate_prompt_registry(entries) == []


def test_prompt_registry_hashes_are_stable():
    entries = iter_prompt_registry()
    electrical = next(entry for entry in entries if entry.prompt_id == "opendatasheet.electrical.vision")

    from extractors.electrical import VISION_PROMPT

    assert electrical.prompt_sha256 == hashlib.sha256(VISION_PROMPT.encode("utf-8")).hexdigest()
    assert electrical.prompt_length == len(VISION_PROMPT)


def test_prompt_registry_validation_catches_untracked_shape():
    entries = [
        PromptRegistryEntry(
            prompt_id="bad.prompt",
            prompt_version="v1",
            owner_module="extractors.fake",
            prompt_attr="PROMPT",
            prompt_sha256="not-a-hash",
            prompt_length=20,
        ),
        PromptRegistryEntry(
            prompt_id="bad.prompt",
            prompt_version="1.0.0",
            owner_module="extractors.fake2",
            prompt_attr="PROMPT",
            prompt_sha256="0" * 64,
            prompt_length=200,
        ),
    ]

    errors = validate_prompt_registry(entries)

    assert any("must start" in error for error in errors)
    assert any("duplicate" in error for error in errors)
    assert any("semver" in error for error in errors)
    assert any("unexpectedly short" in error for error in errors)
    assert any("prompt_sha256" in error for error in errors)
