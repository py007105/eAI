from engine.dedupe import ReleaseGrace, Suppressor


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


def test_callers_of_a_service_in_release_grace_are_covered_too():
    """Regression (live smoke test): a bad inventory release made orders and web fail first; flagging them while inventory
    was still in grace opened an incident on the wrong service."""
    from engine.dedupe import downstream_of
    topo = {"web": ["orders", "inventory"], "orders": ["inventory", "payments"], "inventory": [], "payments": []}
    assert downstream_of("web", topo) == {"orders", "inventory", "payments"}
    assert downstream_of("orders", topo) == {"inventory", "payments"} and downstream_of("inventory", topo) == set()
    in_grace = {"web": False, "orders": False, "inventory": True, "payments": False}   # inventory was just released

    def covered(s):
        return in_grace[s] or any(in_grace[d] for d in downstream_of(s, topo))
    assert covered("inventory") and covered("orders") and covered("web")   # all depend on the released service
    assert not covered("payments")                                          # an unrelated service is still judged


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
