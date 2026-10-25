from listing import build_actions, normalize_text, parse_list_line


def test_marcadores_e_numeracao():
    for line in ["• a", "- a", "* a", "– a", "▪ a", "○ a", "1. a", "1) a", "a) a", "12. a"]:
        item = parse_list_line(line)
        assert item is not None, line
        assert item.text == "a"


def test_nao_lista():
    for line in ["", "texto", "-sem espaço", "1.5 kg", "---", "**negrito**", "   "]:
        assert parse_list_line(line) is None, line


def test_recuo_preservado():
    item = parse_list_line("    - sub")
    assert item.indent == "    " and item.indent_width == 4
    assert parse_list_line("\t• x").indent_width == 4


def test_marcadores_privados_do_word():
    assert normalize_text(" a\n b") == "• a\n▪ b"


def test_sem_auto_list_literal():
    actions = build_actions("- a\n\t- b\n\n1. c", auto_list=False)
    chars = "".join("\n" if k == "enter" else "\t" if k == "tab" else c for k, c in actions)
    assert chars == "- a\n\t- b\n\n1. c"


def kinds(actions):
    return [("T" if k == "char" else k) for k, _ in actions]


def typed(actions):
    return "".join(c for k, c in actions if k == "char")


def test_auto_list_marcador_so_no_primeiro():
    actions = build_actions("- a\n- b\n- c", auto_list=True)
    assert typed(actions) == "- abc"
    assert kinds(actions).count("enter_plain") == 2


def test_auto_list_subnivel_e_volta():
    actions = build_actions("1. a\n   - b\n1. c", auto_list=True)
    ks = kinds(actions)
    assert ks.count("tab") == 1 and ks.count("shift_tab") == 1
    assert ks.index("tab") < ks.index("shift_tab")


def test_auto_list_saida_do_bloco():
    actions = build_actions("- a\n- b\nfim", auto_list=True)
    ks = kinds(actions)
    # Depois de "b": Enter (novo item) + Enter (sai da lista), sem "enter" comum
    assert ks[-5:] == ["enter_plain", "enter_plain", "T", "T", "T"]
    assert "enter" not in ks


def test_auto_list_sem_saida_no_fim_do_texto():
    assert kinds(build_actions("- a\n- b", auto_list=True))[-1] == "T"


def test_linha_em_branco_encerra_bloco():
    actions = build_actions("- a\n\n- b", auto_list=True)
    assert typed(actions) == "- a- b"
    assert kinds(actions).count("enter") == 1


def test_auto_list_bullet_simbolo_vira_hifen():
    for symbol in "•▪○–*":
        assert typed(build_actions(f"{symbol} a\n{symbol} b", auto_list=True)) == "- ab"


def test_auto_list_numeracao_preservada():
    assert typed(build_actions("1) a\n2) b", auto_list=True)) == "1) ab"
    assert typed(build_actions("a) x\nb) y", auto_list=True)) == "a) xy"


def test_travessao_longo_nao_e_lista():
    assert parse_list_line("— Olá, disse ele.") is None
    assert typed(build_actions("— Olá\n— Oi", auto_list=True)) == "— Olá— Oi"
    assert "enter_plain" not in kinds(build_actions("— Olá\n— Oi", auto_list=True))
