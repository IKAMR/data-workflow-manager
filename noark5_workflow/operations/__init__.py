from .build_noark5_depot_report import BuildNoark5DepotReportOperation
from .compose_noark5_views import ComposeNoark5ViewsOperation
from .analyse_arkivstruktur import AnalyseArkivstrukturOperation
from .analyse_noark5_core import AnalyseNoark5CoreOperation
from .analyse_noark5_u1 import AnalyseNoark5U1Operation
from .dias_package import DiasPackageOperation
from .import_arkade5_reports import ImportArkade5ReportsOperation
from .metadata_inventory import MetadataInventoryOperation
from .run_arkade5_cli import Arkade5Noark5TestOperation, Arkade5PronomAnalysisOperation
from .run_noark5_xpath_tests import (
    RunNoark5XpathRegressionOperation,
    RunNoark5XpathTestsOperation,
)
from .validate_xml_schema import ValidateXmlSchemaOperation

__all__ = [
    "BuildNoark5DepotReportOperation",
    "ComposeNoark5ViewsOperation",
    "AnalyseArkivstrukturOperation",
    "AnalyseNoark5CoreOperation",
    "AnalyseNoark5U1Operation",
    "DiasPackageOperation",
    "ImportArkade5ReportsOperation",
    "MetadataInventoryOperation",
    "Arkade5Noark5TestOperation",
    "Arkade5PronomAnalysisOperation",
    "RunNoark5XpathRegressionOperation",
    "RunNoark5XpathTestsOperation",
    "ValidateXmlSchemaOperation",
]
