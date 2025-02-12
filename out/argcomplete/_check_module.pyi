from _typeshed import Incomplete
from typing import NamedTuple

class ModuleSpec(NamedTuple):
    origin: Incomplete
    has_location: Incomplete
    submodule_search_locations: Incomplete

class ArgcompleteMarkerNotFound(RuntimeError): ...

def find(name, return_package: bool = False): ...
def main() -> None: ...
