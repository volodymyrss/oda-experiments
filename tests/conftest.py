import pytest

import odatestsapp 

@pytest.fixture
def app():
    app = odatestsapp.app
    return app
