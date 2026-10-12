"""tests/test_adapters_genoffice.py: Unit tests cho GenOfficeAdapter."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from adapters.genoffice import (
    GenOfficeAdapter,
    GenOfficeExecutionError,
    GenOfficeNotAvailableError,
    GenOfficeTimeoutError,
)


class TestGenOfficeAdapter:
    def test_preflight_binary_not_found(self):
        adapter = GenOfficeAdapter(binary_path="non_existent_binary_xyz_123")
        res = adapter.preflight()
        assert res["available"] is False
        assert "Không tìm thấy" in res["error"]
        assert res["version"] is None

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_preflight_success(self, mock_run, mock_which):
        mock_which.return_value = "/usr/local/bin/genoffice"
        mock_run.return_value = MagicMock(returncode=0, stdout="GenOffice v1.2.0\n")

        adapter = GenOfficeAdapter(binary_path="genoffice")
        res = adapter.preflight()
        assert res["available"] is True
        assert res["version"] == "GenOffice v1.2.0"
        assert res["error"] is None

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_preflight_timeout(self, mock_run, mock_which):
        mock_which.return_value = "/usr/local/bin/genoffice"
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="genoffice --version", timeout=10)

        adapter = GenOfficeAdapter(binary_path="genoffice")
        res = adapter.preflight()
        assert res["available"] is False
        assert "Timeout" in res["error"]

    def test_build_deck_missing_spec_file(self, tmp_path):
        adapter = GenOfficeAdapter()
        with pytest.raises(FileNotFoundError):
            adapter.build_deck(
                deck_spec_path=tmp_path / "missing_spec.json",
                output_pptx_path=tmp_path / "out.pptx",
            )

    def test_build_deck_not_available_raises_gracefully(self, tmp_path):
        spec_file = tmp_path / "spec.json"
        spec_file.write_text("{}", encoding="utf-8")

        adapter = GenOfficeAdapter(binary_path="non_existent_bin")
        with pytest.raises(GenOfficeNotAvailableError) as exc:
            adapter.build_deck(
                deck_spec_path=spec_file,
                output_pptx_path=tmp_path / "out.pptx",
            )
        assert "chưa sẵn sàng" in str(exc.value)

    @patch.object(GenOfficeAdapter, "preflight")
    @patch("subprocess.run")
    def test_build_deck_success(self, mock_run, mock_preflight, tmp_path):
        mock_preflight.return_value = {
            "available": True,
            "binary_path": "/bin/mock_genoffice",
            "error": None,
        }

        spec_file = tmp_path / "spec.json"
        spec_file.write_text("{}", encoding="utf-8")
        out_pptx = tmp_path / "out.pptx"

        def fake_run(cmd, **kwargs):
            # Giả lập lệnh tạo file pptx có dung lượng > 0
            out_pptx.write_bytes(b"PK\x03\x04fake_pptx_binary_content")
            return MagicMock(returncode=0, stdout="Build completed successfully\n", stderr="")

        mock_run.side_effect = fake_run

        adapter = GenOfficeAdapter()
        res = adapter.build_deck(spec_file, out_pptx, template_name="academic")

        assert res["success"] is True
        assert res["output_path"] == str(out_pptx)
        assert out_pptx.exists()

    @patch.object(GenOfficeAdapter, "preflight")
    @patch("subprocess.run")
    def test_build_deck_execution_error(self, mock_run, mock_preflight, tmp_path):
        mock_preflight.return_value = {
            "available": True,
            "binary_path": "/bin/mock_genoffice",
            "error": None,
        }
        spec_file = tmp_path / "spec.json"
        spec_file.write_text("{}", encoding="utf-8")
        out_pptx = tmp_path / "out.pptx"

        mock_run.return_value = MagicMock(returncode=1, stderr="Template not found")

        adapter = GenOfficeAdapter()
        with pytest.raises(GenOfficeExecutionError) as exc:
            adapter.build_deck(spec_file, out_pptx)
        assert "Template not found" in str(exc.value)

    @patch.object(GenOfficeAdapter, "preflight")
    @patch("subprocess.run")
    def test_build_deck_timeout(self, mock_run, mock_preflight, tmp_path):
        mock_preflight.return_value = {
            "available": True,
            "binary_path": "/bin/mock_genoffice",
            "error": None,
        }
        spec_file = tmp_path / "spec.json"
        spec_file.write_text("{}", encoding="utf-8")
        out_pptx = tmp_path / "out.pptx"

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="build", timeout=5)

        adapter = GenOfficeAdapter(default_timeout=5)
        with pytest.raises(GenOfficeTimeoutError):
            adapter.build_deck(spec_file, out_pptx)

