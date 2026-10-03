"""Isolated browser acceptance server. Never uses real WeChat credentials."""

import tempfile
import time
from sqlalchemy import insert
from publisher.backend.main import create_app, password_hasher
from publisher.backend import db
from publisher.tests.test_workflow import FakeWeChat

_data = tempfile.TemporaryDirectory(prefix="publisher-browser-")
app = create_app(_data.name, testing=True, wechat=FakeWeChat())
with app.state.engine.begin() as c:
    c.execute(
        insert(db.users).values(
            username="admin",
            password_hash=password_hasher.hash("browser-test-password"),
            role="ADMIN",
            status="active",
            created_at=time.time(),
        )
    )
