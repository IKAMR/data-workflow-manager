from .arkivstruktur import ArkivstrukturAnalysis, analyse_arkivstruktur
from .defined_fields import extract_defined_fields, load_definition
from .a13_large_xml import install as _install_a13_large_xml

_install_a13_large_xml()

__all__ = [
    "ArkivstrukturAnalysis",
    "analyse_arkivstruktur",
    "extract_defined_fields",
    "load_definition",
]
