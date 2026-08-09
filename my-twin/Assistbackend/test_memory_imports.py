import importlib
import sys
import unittest


class FirebaseImportRegressionTest(unittest.TestCase):
    def test_assistant_reload_does_not_reinit_firebase(self):
        for name in ["Assist", "Relevant_memory"]:
            sys.modules.pop(name, None)

        assistant = importlib.import_module("Assist")
        reloaded = importlib.reload(assistant)

        self.assertTrue(hasattr(reloaded, "firebase_app"))
        self.assertTrue(hasattr(reloaded, "db"))


if __name__ == "__main__":
    unittest.main()
