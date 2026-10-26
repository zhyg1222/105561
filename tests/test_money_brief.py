import tempfile, unittest
from pathlib import Path
from xiaojuju_core.money_brief import build_brief_text, save_brief

class MoneyBriefTests(unittest.TestCase):
    def test_fallback_uses_real_titles(self):
        rows=[{"goal":"研究：AI自动化服务","status":"done","result_path":"x.md"}]
        text=build_brief_text(rows,[{"topic":"下一项研究"}],model_fn=lambda s,u:"")
        self.assertIn("AI自动化服务",text)
        self.assertIn("下一项研究",text)
    def test_save_brief(self):
        with tempfile.TemporaryDirectory() as d:
            p=save_brief("2026-10-26","测试简报",Path(d))
            self.assertEqual(p.read_text(encoding="utf-8").strip(),"测试简报")