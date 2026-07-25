from mtg_sorter.algorithms.commander_rules import (
    COMMANDER_DECK_SIZE,
    CommanderCard,
    CommanderRuleKind,
    PartnerAbility,
    allowed_color_identity,
    allows_any_number_named,
    deck_list_size,
    evaluate_deck,
    format_identity,
    is_legal_pairing,
    partner_abilities,
    singleton_max_copies,
)

THRASIOS_TEXT = (
    "Partner (You can have two commanders if both have partner.)\n"
    "{4}: Scry 1, then draw a card."
)
TYMNA_TEXT = (
    "Partner (You can have two commanders if both have partner.)\n"
    "At the beginning of your postcombat main phase, you may pay life."
)
WILSON_TEXT = (
    "Partner with Proud Mentor (When this creature enters, target opponent may "
    "put Proud Mentor into their hand.)\nTrample"
)
WYLL_TEXT = (
    "Choose a Background (You can have a Background as a second commander.)\n"
    "Whenever Wyll attacks, create a Treasure token."
)
BACKGROUND_TEXT = "Commander creatures you own have vigilance."
LURRUS_TEXT = (
    "Companion — Each permanent card in your starting deck has mana value 2 or less.\n"
    "During each of your turns, you may cast one permanent spell."
)


def commander(name: str, **kwargs) -> CommanderCard:
    defaults = {
        "oracle_id": name.casefold(),
        "name": name,
        "role": "COMMANDER",
        "color_identity": "",
        "oracle_text": None,
        "type_line": "Legendary Creature — Human",
    }
    defaults.update(kwargs)
    return CommanderCard(**defaults)


def pad_to_commander_size(cards: list[CommanderCard]) -> list[CommanderCard]:
    """Fill with basics so size checks do not drown other assertions."""
    missing = COMMANDER_DECK_SIZE - deck_list_size(cards)
    if missing <= 0:
        return cards
    return [
        *cards,
        CommanderCard(
            "pad-basic",
            "Forest",
            "MAIN",
            "",
            None,
            "Basic Land — Forest",
            quantity=missing,
            is_basic_land=True,
        ),
    ]


def test_partner_abilities_distinguish_plain_partner_from_partner_with() -> None:
    assert partner_abilities(THRASIOS_TEXT) == frozenset({PartnerAbility.PARTNER})
    assert partner_abilities(WILSON_TEXT) == frozenset({PartnerAbility.PARTNER_WITH})
    assert partner_abilities(WYLL_TEXT) == frozenset(
        {PartnerAbility.CHOOSE_A_BACKGROUND}
    )
    assert partner_abilities(LURRUS_TEXT) == frozenset({PartnerAbility.COMPANION})
    assert partner_abilities(None) == frozenset()


def test_partner_abilities_detect_restricted_partner() -> None:
    text = "Partner—Survivors (You can have two commanders if both have Partner—Survivors.)"
    abilities = partner_abilities(text)

    assert PartnerAbility.RESTRICTED_PARTNER in abilities
    assert PartnerAbility.PARTNER not in abilities


def test_two_plain_partners_are_a_legal_pairing() -> None:
    thrasios = commander("Thrasios", oracle_text=THRASIOS_TEXT, color_identity="GU")
    tymna = commander(
        "Tymna", role="PARTNER", oracle_text=TYMNA_TEXT, color_identity="WB"
    )

    assert is_legal_pairing(thrasios, tymna)


def test_plain_partner_with_a_non_partner_is_flagged() -> None:
    thrasios = commander("Thrasios", oracle_text=THRASIOS_TEXT, color_identity="GU")
    vanilla = commander("Random Legend", role="PARTNER", color_identity="R")

    assert not is_legal_pairing(thrasios, vanilla)


def test_partner_with_matches_the_named_card() -> None:
    wilson = commander("Wilson", oracle_text=WILSON_TEXT, color_identity="G")
    mentor = commander("Proud Mentor", role="PARTNER", color_identity="G")
    stranger = commander("Someone Else", role="PARTNER", color_identity="G")

    assert is_legal_pairing(wilson, mentor)
    assert not is_legal_pairing(wilson, stranger)


def test_background_needs_choose_a_background_and_the_right_type() -> None:
    wyll = commander("Wyll", oracle_text=WYLL_TEXT, color_identity="R")
    background = commander(
        "Raised by Giants",
        role="BACKGROUND",
        oracle_text=BACKGROUND_TEXT,
        type_line="Legendary Enchantment — Background",
        color_identity="R",
    )
    not_a_background = commander(
        "Some Legend",
        role="BACKGROUND",
        type_line="Legendary Creature — Elf",
        color_identity="G",
    )
    plain = commander("Plain Commander", color_identity="R")

    assert is_legal_pairing(wyll, background)
    assert not is_legal_pairing(wyll, not_a_background)
    assert not is_legal_pairing(plain, background)


def test_companion_extends_nothing_but_must_fit_the_identity() -> None:
    mono_black = commander("Mono Black", color_identity="B")
    lurrus = commander(
        "Lurrus",
        role="COMPANION",
        oracle_text=LURRUS_TEXT,
        color_identity="WB",
    )

    assert allowed_color_identity([mono_black, lurrus]) == frozenset({"B"})

    issues = evaluate_deck(pad_to_commander_size([mono_black, lurrus]))
    kinds = {issue.kind for issue in issues}

    assert CommanderRuleKind.COLOR_IDENTITY in kinds
    assert CommanderRuleKind.PAIRING not in kinds


def test_evaluate_deck_flags_cards_outside_the_color_identity() -> None:
    cards = pad_to_commander_size(
        [
            commander("Ghen", color_identity="WBR"),
            CommanderCard("ok", "Anguished Unmaking", "MAIN", "WB", None, None),
            CommanderCard("bad", "Cultivate", "MAIN", "G", None, None),
            CommanderCard("colorless", "Sol Ring", "MAIN", "", None, None),
        ]
    )

    issues = [
        issue
        for issue in evaluate_deck(cards)
        if issue.kind is CommanderRuleKind.COLOR_IDENTITY
    ]

    assert len(issues) == 1
    assert issues[0].name == "Cultivate"
    assert issues[0].colors == "G"
    assert issues[0].allowed == "WBR"


def test_partner_identities_are_combined() -> None:
    cards = pad_to_commander_size(
        [
            commander("Thrasios", oracle_text=THRASIOS_TEXT, color_identity="GU"),
            commander(
                "Tymna", role="PARTNER", oracle_text=TYMNA_TEXT, color_identity="WB"
            ),
            CommanderCard("ok", "Anguished Unmaking", "MAIN", "WB", None, None),
            CommanderCard("ok2", "Simic Growth", "MAIN", "GU", None, None),
            CommanderCard("bad", "Lightning Bolt", "MAIN", "R", None, None),
        ]
    )

    issues = [
        issue
        for issue in evaluate_deck(cards)
        if issue.kind is CommanderRuleKind.COLOR_IDENTITY
    ]

    assert [issue.name for issue in issues] == ["Lightning Bolt"]
    assert issues[0].allowed == "WUBG"


def test_missing_scryfall_data_is_reported_separately() -> None:
    cards = pad_to_commander_size(
        [
            commander("Ghen", color_identity="WBR"),
            CommanderCard("unknown", "Uncached Card", "MAIN", None, None, None),
        ]
    )

    issues = [
        issue
        for issue in evaluate_deck(cards)
        if issue.kind is CommanderRuleKind.MISSING_DATA
    ]

    assert len(issues) == 1
    assert issues[0].name == "Uncached Card"


def test_deck_without_commander_reports_nothing() -> None:
    cards = [CommanderCard("bad", "Cultivate", "MAIN", "G", None, None)]

    assert evaluate_deck(cards) == []


def test_singleton_flags_non_basic_duplicates() -> None:
    cards = pad_to_commander_size(
        [
            commander("Ghen", color_identity="WBR"),
            CommanderCard("sr", "Sol Ring", "MAIN", "", None, None, quantity=2),
        ]
    )

    issues = [
        issue
        for issue in evaluate_deck(cards)
        if issue.kind is CommanderRuleKind.SINGLETON
    ]

    assert len(issues) == 1
    assert issues[0].name == "Sol Ring"
    assert issues[0].quantity == 2


def test_basics_are_exempt_from_singleton() -> None:
    cards = pad_to_commander_size(
        [
            commander("Ghen", color_identity="WBR"),
            CommanderCard(
                "plains",
                "Plains",
                "MAIN",
                "W",
                None,
                "Basic Land — Plains",
                quantity=20,
                is_basic_land=True,
            ),
        ]
    )

    assert all(issue.kind is not CommanderRuleKind.SINGLETON for issue in evaluate_deck(cards))


def test_any_number_named_cards_are_exempt_from_singleton() -> None:
    rats_text = (
        "A deck can have any number of cards named Relentless Rats.\n"
        "Relentless Rats gets +1/+1 for each other creature on the battlefield "
        "named Relentless Rats."
    )
    cards = pad_to_commander_size(
        [
            commander("Ghen", color_identity="WBR"),
            CommanderCard(
                "rats",
                "Relentless Rats",
                "MAIN",
                "B",
                rats_text,
                "Creature — Rat",
                quantity=30,
            ),
            CommanderCard(
                "sol",
                "Sol Ring",
                "MAIN",
                "",
                None,
                "Artifact",
                quantity=2,
            ),
        ]
    )

    issues = [
        issue
        for issue in evaluate_deck(cards)
        if issue.kind is CommanderRuleKind.SINGLETON
    ]

    assert [issue.name for issue in issues] == ["Sol Ring"]
    assert allows_any_number_named(rats_text)
    assert not allows_any_number_named("Draw a card.")
    assert singleton_max_copies(rats_text) is None
    assert singleton_max_copies(None) == 1


def test_up_to_n_named_cards_respect_the_printed_cap() -> None:
    dwarves_text = (
        "A deck can have up to seven cards named Seven Dwarves.\n"
        "When Seven Dwarves enters, you gain 2 life."
    )
    ok = pad_to_commander_size(
        [
            commander("Ghen", color_identity="WBR"),
            CommanderCard(
                "dwarf",
                "Seven Dwarves",
                "MAIN",
                "R",
                dwarves_text,
                "Creature — Dwarf",
                quantity=7,
            ),
        ]
    )
    assert all(
        issue.kind is not CommanderRuleKind.SINGLETON for issue in evaluate_deck(ok)
    )
    assert singleton_max_copies(dwarves_text) == 7

    too_many = pad_to_commander_size(
        [
            commander("Ghen", color_identity="WBR"),
            CommanderCard(
                "dwarf",
                "Seven Dwarves",
                "MAIN",
                "R",
                dwarves_text,
                "Creature — Dwarf",
                quantity=8,
            ),
        ]
    )
    issues = [
        issue
        for issue in evaluate_deck(too_many)
        if issue.kind is CommanderRuleKind.SINGLETON
    ]
    assert len(issues) == 1
    assert issues[0].name == "Seven Dwarves"
    assert issues[0].quantity == 8
    assert issues[0].allowed == "7"


def test_deck_size_flags_wrong_total_and_ignores_companion() -> None:
    short = [
        commander("Ghen", color_identity="WBR"),
        CommanderCard("sr", "Sol Ring", "MAIN", "", None, None),
    ]
    size_issues = [
        issue
        for issue in evaluate_deck(short)
        if issue.kind is CommanderRuleKind.DECK_SIZE
    ]
    assert len(size_issues) == 1
    assert size_issues[0].name == "2"
    assert size_issues[0].allowed == "100"

    with_companion = pad_to_commander_size(
        [
            commander("Mono Black", color_identity="B"),
            commander(
                "Lurrus",
                role="COMPANION",
                oracle_text=LURRUS_TEXT,
                color_identity="B",
            ),
        ]
    )
    assert deck_list_size(with_companion) == COMMANDER_DECK_SIZE
    assert all(
        issue.kind is not CommanderRuleKind.DECK_SIZE
        for issue in evaluate_deck(with_companion)
    )


def test_format_identity_uses_wubrg_order() -> None:
    assert format_identity(frozenset({"B", "W", "G"})) == "WBG"
    assert format_identity(frozenset()) == ""
