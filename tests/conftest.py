import pytest

import odatestsapp 

@pytest.fixture
def app():
    app = odatestsapp.app #create_app()
    #app = odatestsapp.create_app()
    return app
