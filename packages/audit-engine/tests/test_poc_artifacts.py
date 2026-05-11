from pathlib import Path

from audit_engine.poc.artifacts import PoCArtifactStore


def test_workspace_isolation_by_scan_and_finding(tmp_path: Path) -> None:
    store = PoCArtifactStore(root=tmp_path)
    w1 = store.workspace_for(scan_id="scan-A", finding_id="f-1")
    w2 = store.workspace_for(scan_id="scan-A", finding_id="f-2")
    w3 = store.workspace_for(scan_id="scan-B", finding_id="f-1")
    assert w1 != w2 and w1 != w3 and w2 != w3
    assert w1.exists() and w2.exists() and w3.exists()


def test_sanitize_keeps_strings_safe(tmp_path: Path) -> None:
    store = PoCArtifactStore(root=tmp_path)
    w = store.workspace_for(scan_id="../etc/passwd", finding_id="aderyn:weird/id:42")
    # Must not escape the root directory.
    assert tmp_path in w.resolve().parents


def test_save_test_and_log(tmp_path: Path) -> None:
    store = PoCArtifactStore(root=tmp_path)
    w = store.workspace_for(scan_id="s", finding_id="f")
    p = store.save_test(workspace=w, content="contract PoC {}", attempt=1)
    assert p.exists()
    assert "PoC.attempt1.t.sol" in p.name

    log_p = store.save_log(workspace=w, attempt=1, body="forge output")
    assert log_p.exists()
    assert "forge.attempt1.log" in log_p.name


def test_relative_path(tmp_path: Path) -> None:
    store = PoCArtifactStore(root=tmp_path)
    w = store.workspace_for(scan_id="s", finding_id="f")
    p = store.save_test(workspace=w, content="x", attempt=1)
    rel = store.relative(p)
    assert "PoC.attempt1.t.sol" in rel
    assert not rel.startswith("/")
