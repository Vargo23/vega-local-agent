import unittest

from core.command_handler import handle_permissions_command
from permissions import SessionGrantStore


class PermissionCommandTests(unittest.TestCase):
    def test_help_empty_list_revoke_and_clear(self):
        store = SessionGrantStore()
        self.assertIn("/permissions grants", handle_permissions_command("/permissions", store))
        self.assertEqual(handle_permissions_command("/permissions grants", store), "Active session grants: none.")
        store.grant("propose_patch")
        store.grant("memory_add")
        listing = handle_permissions_command("/permissions grants", store)
        self.assertLess(listing.index("memory_add"), listing.index("propose_patch"))
        self.assertEqual(handle_permissions_command("/permissions revoke memory_add", store), "Session grant revoked: memory_add.")
        self.assertIn("was not active", handle_permissions_command("/permissions revoke memory_add", store))
        self.assertEqual(handle_permissions_command("/permissions clear", store), "Cleared 1 session grant(s).")

    def test_no_grant_command_exists(self):
        store = SessionGrantStore()
        self.assertIn("/permissions grants", handle_permissions_command("/permissions grant memory_add", store))
        self.assertEqual(store.list_grants(), ())


if __name__ == "__main__":
    unittest.main()
