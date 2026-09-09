import bot

from bot import load_example_context


def test_voice_smoke_uses_only_fictional_reviewed_inputs():
    context = load_example_context()

    assert context.rubric.rubric_id == "software-engineer-demo"
    assert any(source.document_id == "fictional-demo" for source in context.sources)


def test_windows_entrypoint_keeps_utf8_configuration_near_main():
    source = open(bot.__file__, encoding="utf-8").read()

    assert 'reconfigure(encoding="utf-8")' in source
    assert source.index('reconfigure(encoding="utf-8")') < source.rindex("main()")
