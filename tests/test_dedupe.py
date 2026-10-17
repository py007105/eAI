from eternalai.dedupe import ReleaseGrace, Suppressor


def test_release_blip_is_ignored_then_judged():
    g = ReleaseGrace(15.0)
    assert not g.in_grace("orders", 0, 100.0)            # no release yet
    assert g.in_grace("orders", 1, 101.0)                # release becomes visible: grace starts
    assert g.in_grace("orders", 1, 110.0)                # still inside the 15 s grace
    assert not g.in_grace("orders", 1, 117.0)            # grace over: a persistent problem will now count


def test_grace_is_per_service_and_a_rollback_restarts_it():
    g = ReleaseGrace(15.0)
    g.in_grace("web", 1, 100.0)
    assert not g.in_grace("payments", 0, 105.0)          # another service is unaffected
    assert not g.in_grace("web", 1, 120.0)
    assert g.in_grace("web", 2, 130.0)                   # a rollback is another release change (counter 1 -> 2)


def test_unresolved_incident_suppresses_reopening_until_quiet():
    s = Suppressor(quiet_ticks=3)
    s.note_incident("escalated", ["inventory"])
    assert s.filter({"inventory", "web"}) == {"web"}
    for _ in range(5):                                   # still anomalous: stays suppressed
        s.update({"inventory": True})
    assert s.filter({"inventory"}) == set()
    for _ in range(3):                                   # quiet for 3 ticks: released
        s.update({"inventory": False})
    assert s.filter({"inventory"}) == {"inventory"}


def test_recovered_incident_does_not_suppress():
    s = Suppressor()
    s.note_incident("recovered", ["orders"])
    assert s.filter({"orders"}) == {"orders"}
