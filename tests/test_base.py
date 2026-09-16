"""
Base test case providing hermetic SQLite and Flask test client isolation.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import os
import sys
import unittest
import tempfile
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import backend.database as db_mod
import backend.server as server_mod
from backend.database import MindFlowDB
from backend.server import app, SHARED_API_TOKEN


class BaseMindFlowTestCase(unittest.TestCase):
    """
    Hermetic base test case.
    Sets up an isolated in-memory or temp-dir SQLite DB and Flask test client with valid headers.
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_mind_flow.db")
        
        # Save previous environment and module state
        self._orig_db_file = getattr(db_mod, "DB_FILE", ":memory:")
        self._orig_env_db = os.environ.get("MINDFLOW_DB_FILE")
        self._orig_server_db = server_mod.db
        
        # Isolate database environment
        os.environ["MINDFLOW_DB_FILE"] = self.db_path
        db_mod.DB_FILE = self.db_path
        
        # Instantiate test database
        self.db = MindFlowDB(db_path=self.db_path)
        server_mod.db = self.db
        
        # Flask test client
        self.client = app.test_client()
        self.valid_headers = {
            "X-MIND-FLOW-TOKEN": SHARED_API_TOKEN,
            "Origin": "http://127.0.0.1:5000",
            "Content-Type": "application/json",
            "Host": "127.0.0.1:5000"
        }

    def get_auth_headers(self, extra=None):
        h = dict(self.valid_headers)
        if extra:
            h.update(extra)
        return h

    def tearDown(self):
        try:
            self.db.flush_queue()
        except Exception:
            pass
        try:
            self.db.close()
        except Exception:
            pass
        
        # Restore server db and paths
        server_mod.db = self._orig_server_db
        db_mod.DB_FILE = self._orig_db_file
        if self._orig_env_db is not None:
            os.environ["MINDFLOW_DB_FILE"] = self._orig_env_db
        else:
            os.environ.pop("MINDFLOW_DB_FILE", None)
            
        if hasattr(server_mod.db, "filepath") and server_mod.db:
            server_mod.db.filepath = self._orig_db_file
        
        # Clean temp dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)
