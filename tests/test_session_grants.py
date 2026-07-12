import unittest

from permissions import PermissionValidationError, SessionGrantError, SessionGrantStore


class SessionGrantStoreTests(unittest.TestCase):
    def test_grant_check_revoke_clear_and_sorted_listing(self):
        store = SessionGrantStore(3)
        store.grant("zeta")
        store.grant("alpha")
        store.grant("alpha")
        self.assertTrue(store.contains("alpha"))
        self.assertEqual(tuple(item.tool_name for item in store.list_grants()), ("alpha", "zeta"))
        self.assertTrue(store.revoke("alpha"))
        self.assertFalse(store.revoke("alpha"))
        self.assertEqual(store.clear(), 1)
        self.assertEqual(store.list_grants(), ())

    def test_invalid_names_and_capacity_fail(self):
        store = SessionGrantStore(1)
        for name in ("", "Invalid Name", " spaced"):
            with self.subTest(name=name), self.assertRaises(PermissionValidationError):
                store.grant(name)
        store.grant("alpha")
        with self.assertRaises(SessionGrantError):
            store.grant("beta")

    def test_instances_do_not_share_state(self):
        first, second = SessionGrantStore(), SessionGrantStore()
        first.grant("memory_add")
        self.assertFalse(second.contains("memory_add"))


if __name__ == "__main__":
    unittest.main()
