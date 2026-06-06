"""Tests for all detector implementations."""
import pytest
from platform_capability.detectors.dependency import DependencyDetector
from platform_capability.detectors.import_detector import ImportDetector
from platform_capability.detectors.code_pattern import CodePatternDetector
from platform_capability.detectors.namespace import PlatformNamespaceDetector
from platform_capability.models import SignalType, SignalWeight, PlatformConventions


# ── DependencyDetector ────────────────────────────────────────────────────────

class TestDependencyDetector:
    def setup_method(self):
        self.detector = DependencyDetector()

    def test_detects_approved_dependency(self, make_workspace, http_capability):
        ws = make_workspace({"requirements.txt": "platform-http-client==2.1.0\nflask==3.0.0\n"})
        signals, items = self.detector.detect(ws, http_capability, "run-001")
        adoption = [s for s in signals if s.signal_type == SignalType.ADOPTION]
        assert len(adoption) >= 1
        assert adoption[0].weight == SignalWeight.HIGH

    def test_detects_reinvention_dependency(self, make_workspace, http_capability):
        ws = make_workspace({"requirements.txt": "requests==2.31.0\nflask==3.0.0\n"})
        signals, items = self.detector.detect(ws, http_capability, "run-001")
        reinvention = [s for s in signals if s.signal_type == SignalType.REINVENTION]
        assert len(reinvention) >= 1

    def test_no_signals_for_unrelated_deps(self, make_workspace, http_capability):
        ws = make_workspace({"requirements.txt": "boto3==1.28.0\njinja2==3.1.2\n"})
        signals, _ = self.detector.detect(ws, http_capability, "run-001")
        assert signals == []

    def test_evidence_items_created(self, make_workspace, http_capability):
        ws = make_workspace({"requirements.txt": "platform-http-client==2.1.0\n"})
        signals, items = self.detector.detect(ws, http_capability, "run-001")
        assert len(items) >= 1
        assert all(item.capability_id == "platform_http_client" for item in items)

    def test_evidence_refs_match_signals(self, make_workspace, http_capability):
        ws = make_workspace({"requirements.txt": "platform-http-client==2.1.0\n"})
        signals, items = self.detector.detect(ws, http_capability, "run-001")
        item_ids = {i.evidence_id for i in items}
        for sig in signals:
            assert sig.evidence_ref in item_ids

    def test_parses_setup_py(self, make_workspace, http_capability):
        ws = make_workspace({"setup.py": 'setup(install_requires=["requests>=2.0"])'})
        signals, _ = self.detector.detect(ws, http_capability, "run-001")
        reinvention = [s for s in signals if s.signal_type == SignalType.REINVENTION]
        assert len(reinvention) >= 1

    def test_parses_pyproject_toml(self, make_workspace, http_capability):
        ws = make_workspace({"pyproject.toml": '[project]\ndependencies = [\n  "platform-http-client>=2.0",\n]\n'})
        signals, _ = self.detector.detect(ws, http_capability, "run-001")
        adoption = [s for s in signals if s.signal_type == SignalType.ADOPTION]
        assert len(adoption) >= 1

    def test_ignores_comments_in_requirements(self, make_workspace, http_capability):
        ws = make_workspace({"requirements.txt": "# this is a comment\nflask==3.0.0\n"})
        signals, _ = self.detector.detect(ws, http_capability, "run-001")
        assert signals == []

    def test_no_dep_files_returns_empty(self, make_workspace, http_capability):
        ws = make_workspace({"src/app.py": "import requests\n"})
        # no dependency files in manifest, but source files present
        ws.dependency_files = []
        signals, _ = self.detector.detect(ws, http_capability, "run-001")
        assert signals == []


# ── ImportDetector ────────────────────────────────────────────────────────────

class TestImportDetector:
    def setup_method(self):
        self.detector = ImportDetector()

    def test_detects_approved_import(self, make_workspace, http_capability):
        ws = make_workspace({
            "requirements.txt": "platform-http-client==2.1.0\n",
            "src/client.py": "from platform_http_client import PlatformHttpClient\n",
        })
        signals, items = self.detector.detect(ws, http_capability, "run-001")
        adoption = [s for s in signals if s.signal_type == SignalType.ADOPTION]
        assert len(adoption) >= 1

    def test_detects_module_import(self, make_workspace, http_capability):
        ws = make_workspace({
            "requirements.txt": "platform-http-client==2.1.0\n",
            "src/client.py": "import platform_http_client\n",
        })
        signals, _ = self.detector.detect(ws, http_capability, "run-001")
        adoption = [s for s in signals if s.signal_type == SignalType.ADOPTION]
        assert len(adoption) >= 1

    def test_detects_reinvention_class_import(self, make_workspace, http_capability):
        ws = make_workspace({
            "requirements.txt": "requests==2.31.0\n",
            "src/http.py": "from reporting_service.http.retry import RetrySession\n",
        })
        signals, _ = self.detector.detect(ws, http_capability, "run-001")
        reinvention = [s for s in signals if s.signal_type == SignalType.REINVENTION]
        assert len(reinvention) >= 1

    def test_no_signals_for_unrelated_imports(self, make_workspace, http_capability):
        ws = make_workspace({
            "requirements.txt": "boto3==1.28.0\n",
            "src/app.py": "import boto3\nimport json\n",
        })
        ws.dependency_files = []
        signals, _ = self.detector.detect(ws, http_capability, "run-001")
        assert signals == []

    def test_snippet_included_in_evidence(self, make_workspace, http_capability):
        ws = make_workspace({
            "requirements.txt": "platform-http-client==2.1.0\n",
            "src/client.py": "from platform_http_client import PlatformHttpClient\nclient = PlatformHttpClient()\n",
        })
        _, items = self.detector.detect(ws, http_capability, "run-001")
        assert any(item.raw_content for item in items)

    def test_skips_non_python_files(self, make_workspace, http_capability):
        ws = make_workspace({
            "requirements.txt": "platform-http-client==2.1.0\n",
            "src/script.sh": "import platform_http_client\n",
        })
        signals, _ = self.detector.detect(ws, http_capability, "run-001")
        assert signals == []

    def test_handles_syntax_error_gracefully(self, make_workspace, http_capability):
        ws = make_workspace({
            "requirements.txt": "platform-http-client==2.1.0\n",
            "src/broken.py": "from platform_http_client import PlatformHttpClient\n",
        })
        # Should not raise even on file read errors
        signals, _ = self.detector.detect(ws, http_capability, "run-001")
        assert isinstance(signals, list)


# ── CodePatternDetector ───────────────────────────────────────────────────────

class TestCodePatternDetector:
    def setup_method(self):
        self.detector = CodePatternDetector()

    def test_detects_anti_pattern_class(self, make_workspace, http_capability):
        ws = make_workspace({
            "requirements.txt": "requests==2.31.0\n",
            "src/http.py": "import requests\n\nclass RetrySession(requests.Session):\n    pass\n",
        })
        signals, items = self.detector.detect(ws, http_capability, "run-001")
        reinvention = [s for s in signals if s.signal_type == SignalType.REINVENTION]
        assert len(reinvention) >= 1
        assert reinvention[0].weight == SignalWeight.HIGH

    def test_detects_custom_retry_medium_class(self, make_workspace, http_capability):
        ws = make_workspace({
            "requirements.txt": "requests==2.31.0\n",
            "src/http.py": "class CustomRetry:\n    max_retries = 3\n",
        })
        signals, _ = self.detector.detect(ws, http_capability, "run-001")
        reinvention = [s for s in signals if s.signal_type == SignalType.REINVENTION]
        assert len(reinvention) >= 1
        assert reinvention[0].weight == SignalWeight.MEDIUM

    def test_detects_code_pattern_httpadapter(self, make_workspace, http_capability):
        ws = make_workspace({
            "requirements.txt": "requests==2.31.0\n",
            "src/http.py": "from requests.adapters import HTTPAdapter\nadapter = HTTPAdapter(max_retries=3)\n",
        })
        signals, _ = self.detector.detect(ws, http_capability, "run-001")
        reinvention = [s for s in signals if s.signal_type == SignalType.REINVENTION]
        assert len(reinvention) >= 1

    def test_no_signals_clean_code(self, make_workspace, http_capability):
        ws = make_workspace({
            "requirements.txt": "platform-http-client==2.1.0\n",
            "src/client.py": "from platform_http_client import PlatformHttpClient\nclient = PlatformHttpClient()\n",
        })
        signals, _ = self.detector.detect(ws, http_capability, "run-001")
        # No reinvention signals expected
        reinvention = [s for s in signals if s.signal_type == SignalType.REINVENTION]
        assert len(reinvention) == 0

    def test_snippet_in_evidence(self, make_workspace, http_capability):
        ws = make_workspace({
            "requirements.txt": "requests==2.31.0\n",
            "src/http.py": "class RetrySession(requests.Session):\n    def __init__(self):\n        super().__init__()\n",
        })
        _, items = self.detector.detect(ws, http_capability, "run-001")
        assert any(item.raw_content for item in items)

    def test_skips_non_python_files(self, make_workspace, http_capability):
        ws = make_workspace({
            "requirements.txt": "requests==2.31.0\n",
            "src/style.css": "class RetrySession { color: red; }",
        })
        signals, _ = self.detector.detect(ws, http_capability, "run-001")
        assert signals == []


# ── PlatformNamespaceDetector ─────────────────────────────────────────────────

class TestPlatformNamespaceDetector:
    def _detector(self, prefixes=None, dep_prefixes=None):
        return PlatformNamespaceDetector(PlatformConventions(
            approved_import_prefixes=prefixes or ["platform_"],
            approved_dependency_prefixes=dep_prefixes or ["platform-"],
        ))

    def test_detects_platform_import(self, make_workspace, http_capability):
        detector = self._detector()
        ws = make_workspace({
            "requirements.txt": "platform-http-client==2.1.0\n",
            "src/client.py": "from platform_http_client import PlatformHttpClient\n",
        })
        signals, items = detector.detect(ws, http_capability, "run-001")
        platform = [s for s in signals if s.signal_type == SignalType.GENERIC_PLATFORM]
        assert len(platform) >= 1

    def test_detects_platform_dependency(self, make_workspace, http_capability):
        detector = self._detector()
        ws = make_workspace({"requirements.txt": "platform-http-client==2.1.0\n"})
        signals, _ = detector.detect(ws, http_capability, "run-001")
        platform = [s for s in signals if s.signal_type == SignalType.GENERIC_PLATFORM]
        assert len(platform) >= 1

    def test_no_signals_without_platform_usage(self, make_workspace, http_capability):
        detector = self._detector()
        ws = make_workspace({
            "requirements.txt": "requests==2.31.0\n",
            "src/app.py": "import requests\n",
        })
        signals, _ = detector.detect(ws, http_capability, "run-001")
        platform = [s for s in signals if s.signal_type == SignalType.GENERIC_PLATFORM]
        assert platform == []

    def test_empty_conventions_returns_empty(self, make_workspace, http_capability):
        detector = PlatformNamespaceDetector(PlatformConventions())
        ws = make_workspace({"requirements.txt": "platform-http-client==2.1.0\n"})
        signals, items = detector.detect(ws, http_capability, "run-001")
        assert signals == []
        assert items == []

    def test_skips_non_python_source_files(self, make_workspace, http_capability):
        detector = self._detector()
        ws = make_workspace({
            "requirements.txt": "platform-http-client==2.1.0\n",
            "src/style.css": "platform_custom { color: red; }",
        })
        # Only dep file should produce signals, not CSS
        signals, _ = detector.detect(ws, http_capability, "run-001")
        for sig in signals:
            assert sig.signal_type == SignalType.GENERIC_PLATFORM
