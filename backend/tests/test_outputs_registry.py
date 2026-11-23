from app.api import contract
from app.outputs import DEFAULT_OUTPUT, DEFAULT_RADIO_CHANNEL, OUTPUTS, WIRED_OUTPUT, display_modes, get_output, output_of_radio


def test_each_output_is_unique_and_reachable_by_its_radio():
    ids = [output.id for output in OUTPUTS]
    radios = [output.radio_channel for output in OUTPUTS]
    assert len(set(ids)) == len(ids) and len(set(radios)) == len(radios)
    for output in OUTPUTS:
        assert get_output(output.id) is output
        assert output_of_radio(output.radio_channel) is output


def test_exactly_one_wired_output_hosts_the_coach():
    assert [output for output in OUTPUTS if output.wired] == [WIRED_OUTPUT]
    assert all(output.wired for output in OUTPUTS if output.coach)


def test_every_output_offers_kiosk_and_known_modes_only():
    for output in OUTPUTS:
        assert output.modes[0] == "kiosk"
        assert set(output.modes) <= set(display_modes())


def test_contract_lists_are_derived_from_the_table():
    assert contract.CHANNELS == tuple(output.id for output in OUTPUTS)
    assert contract.DEFAULT_CHANNEL == DEFAULT_OUTPUT.id
    assert contract.RADIO_CHANNELS == tuple(output.radio_channel for output in OUTPUTS)
    assert contract.RADIO_OUTPUTS == {output.id: output.radio_channel for output in OUTPUTS}
    assert contract.COACH_CHANNELS == tuple(output.id for output in OUTPUTS if output.coach)
    assert DEFAULT_RADIO_CHANNEL in contract.RADIO_CHANNELS
