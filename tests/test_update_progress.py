import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools/scripts'))
import update_progress

class UpdateTests(unittest.TestCase):
    def test_missing_untracked_receipt_still_renders_eu(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(update_progress,'ROOT',pathlib.Path(directory)), patch.object(update_progress.subprocess,'run') as run:
                update_progress.main()
            self.assertEqual(run.call_count,3)
            usa=run.call_args_list[1].args[0]
            self.assertEqual(usa[usa.index('--out')+1],'docs/progress/usa')
            eu=run.call_args_list[2].args[0]
            self.assertEqual(eu[eu.index('--out')+1],'docs/progress')
            self.assertIn('tools/scripts/region_progress.py',run.call_args_list[-1].args[0])

if __name__=='__main__':unittest.main()
