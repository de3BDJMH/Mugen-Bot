from pydantic import BaseModel

from ...libraries.tools import *
from ...libraries.pluginmanage.tools import *
from ...libraries.finaltest.test import *

class Config(BaseModel):
    """Plugin Config Here"""
    TESTS:dict={"test":Test("")}#所有人的题集

