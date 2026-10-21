import tempfile
import unittest
from pathlib import Path
from tools.recovery_bundle import seal, restore, _name


class RecoveryBundleTests(unittest.TestCase):
    def test_round_trip_binary_unicode_without_cleartext(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary);archive=root/'backups/snapshot.vrb';key=root/'keys/key.bin'
            files={'data.json':'{"mensagem":"Restauração çã"}'.encode(), 'files/a.pdf':b'%PDF-\x00\xff'}
            seal(files,archive,key)
            self.assertNotIn(b'%PDF-', archive.read_bytes())
            self.assertEqual(restore(archive,key,root/'restored'),{'files':2,'verified':True})
            for name,data in files.items():self.assertEqual((root/'restored'/name).read_bytes(),data)

    def test_tampering_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);archive=root/'b/a';key=root/'k/a';seal({'a':b'secret'},archive,key)
            raw=bytearray(archive.read_bytes());raw[-1]^=1;archive.write_bytes(raw)
            with self.assertRaises(Exception):restore(archive,key,root/'restored')
            self.assertFalse((root/'restored').exists())

    def test_key_must_be_separate_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            with self.assertRaises(ValueError):seal({'a':b'x'},root/'a',root/'key')
            seal({'a':b'x'},root/'b/a',root/'k/a')
            with self.assertRaises(ValueError):seal({'a':b'x'},root/'b/new',root/'k/a')

    def test_existing_destination_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);seal({'a':b'x'},root/'b/a',root/'k/a');(root/'existing').mkdir()
            (root/'existing/user.env').write_text('preserved')
            with self.assertRaises(ValueError):restore(root/'b/a',root/'k/a',root/'existing')
            self.assertEqual((root/'existing/user.env').read_text(),'preserved')

    def test_reject_unsafe_paths(self):
        for name in ('../secret','/absolute','C:/Windows/a','dir/../../a','dir\\file','./file','dir//file'):
            with self.subTest(name=name),self.assertRaises(ValueError):_name(name)


if __name__=='__main__':unittest.main()
