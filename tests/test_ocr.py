import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ocr import _normalize_ocr_text, _score_text, sync_run_ocr


class OCRHelpersTest(unittest.TestCase):
    def test_score_text_prefers_meaningful_text(self):
        self.assertGreater(_score_text("Hello 123"), _score_text("@@@???"))

    def test_normalize_ocr_text_collapses_cjk_spacing(self):
        self.assertEqual(_normalize_ocr_text("你 好 ， 世 界"), "你好，世界")


class OCRPipelineTest(unittest.TestCase):
    @patch("ocr.capture_region")
    @patch("ocr._run_powershell_ocr")
    def test_sync_run_ocr_picks_best_variant(self, mock_run_powershell_ocr, mock_capture_region):
        bmp = bytearray(54 + 12)
        bmp[0:2] = b"BM"
        bmp[18:22] = (2).to_bytes(4, "little", signed=True)
        bmp[22:26] = (2).to_bytes(4, "little", signed=True)
        mock_capture_region.return_value = bytes(bmp)
        mock_run_powershell_ocr.side_effect = ["", "tiny", "clear text", "", "", ""]

        result = sync_run_ocr((0, 0, 20, 20))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["text"], "clear text")

    @patch("ocr.capture_region")
    @patch("ocr._run_powershell_ocr")
    def test_sync_run_ocr_marks_low_confidence_for_small_selection(self, mock_run_powershell_ocr, mock_capture_region):
        bmp = bytearray(54 + 12)
        bmp[0:2] = b"BM"
        bmp[18:22] = (2).to_bytes(4, "little", signed=True)
        bmp[22:26] = (2).to_bytes(4, "little", signed=True)
        mock_capture_region.return_value = bytes(bmp)
        mock_run_powershell_ocr.side_effect = ["", "", "", "", "", "", "", "", ""]

        result = sync_run_ocr((0, 0, 20, 20))

        self.assertEqual(result["status"], "low_confidence")
        self.assertIsNone(result["text"])


if __name__ == "__main__":
    unittest.main()
